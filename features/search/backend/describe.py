"""«✨ Опиши»: фраза гостя → какие линзы включить и какой месяц. Это не чат: ответ — настройки интерфейса.

Без ключа LLM работают правила: регулярки для основных линз и синонимы фильтров «что рядом»
(«магазин у дома» → «Продуктовый рядом»), сравнение по основам слов. С ключом (LLM_* в .env)
фразу разбирает модель, но выбирать она может только из существующих линз — факты она не создаёт.
Чего мы пока не считаем (тишина, питомцы в отеле…), называем честно в not_yet.
"""
import json
import logging
import re
import urllib.request

from core.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

from .lenses import BY_ID, LENSES

log = logging.getLogger(__name__)

RULES = [  # (регулярка, линзы) — порядок важен: «вид на море» раньше просто «моря»
    (r"вид\w* на мор|мор\w* из окн|мор\w* в окн|видн\w* мор|панорам", ["sea_view"]),
    (r"закат", ["sunset"]),
    (r"пляж|у моря|к морю|от моря|рядом с морем|перв\w* лини|на море|до моря", ["beach_near"]),
    (r"без подъ[её]м|не в гору|без горк|ровн|коляск|пожил|тяжело ходить|с реб[её]нк|с детьми|дет[еяи]", ["flat", "beach_near"]),
]
NOT_YET = [  # (регулярка, как назвать) — честно говорим, что этого пока не знаем
    (r"тих|шум|спать|выспат", "тишина"),
    (r"с собак|с кошк|с питом|с животн|с пс[оа]м", "можно ли с питомцем"),
    (r"удал[её]н|интернет|связь|wi-?fi|вайфай", "связь для работы"),
]
MONTHS = ["январ", "феврал", "март", "апрел", "ма[йяе]", "июн", "июл", "август",
          "сентябр", "октябр", "ноябр", "декабр"]


def describe(text: str) -> dict:
    out = _llm(text) if LLM_API_KEY and LLM_BASE_URL else None
    if out is None:
        out = _rules(text)
    return out


def _words(text: str) -> list[str]:
    t = text.lower().replace("ё", "е").replace("/", "")
    return re.findall(r"[a-zа-я0-9]+", t)


def _stem(w: str) -> str:
    return w if len(w) <= 4 else w[:max(4, len(w) - 2)]


def _find(stems: list[str], words: list[str]) -> set[int] | None:
    """Позиции слов фразы, где по порядку встречаются все основы синонима (окно — длина синонима + 2)."""
    for start in range(len(words)):
        pos, i = [], start
        for st in stems:
            while i < len(words) and i - start <= len(stems) + 2:
                if words[i].startswith(st) and len(words[i]) - len(st) <= 3:
                    pos.append(i)
                    i += 1
                    break
                i += 1
            else:
                break
        if len(pos) == len(stems):
            return set(pos)
    return None


def _catalog(text: str) -> list[str]:
    """Фильтры «что рядом» по синонимам. Длинный синоним побеждает короткий внутри себя:
    «круглосуточная аптека» — это «Аптека круглосуточно», а не ещё и просто «Аптека»."""
    words = _words(text)
    found = []
    for l in LENSES:
        for syn in l.get("synonyms", []):
            stems = [_stem(w) for w in _words(syn) if len(w) > 2 or w in ("тц", "жд")]
            pos = _find(stems, words) if stems else None
            if pos:
                found.append((len(pos), pos, l["id"]))
    taken, out = [], []
    for n, pos, lid in sorted(found, key=lambda x: -x[0]):
        if lid in out or any(pos < p for p in taken):
            continue
        taken.append(pos)
        out.append(lid)
    return out


def _rules(text: str) -> dict:
    t = text.lower()
    lenses = []
    for rx, ids in RULES:
        if re.search(rx, t):
            lenses += [i for i in ids if i not in lenses]
    lenses += [i for i in _catalog(text) if i not in lenses]
    if "sea_view" in lenses and "beach_near" in lenses and not re.search(r"пляж|у моря|к морю|от моря|до моря", t):
        lenses.remove("beach_near")   # «вид на море» сам по себе не значит «рядом пляж»
    month = next((i + 1 for i, rx in enumerate(MONTHS) if re.search(rf"\b{rx}", t)), None)
    not_yet = [name for rx, name in NOT_YET if re.search(rx, t)]
    return {"lenses": lenses, "month": month, "not_yet": not_yet, "by": "rules"}


def _llm(text: str) -> dict | None:
    menu = "\n".join(f"- {l['id']}: {l['title']} ({l['hint']})" for l in LENSES)
    prompt = (f"Гость описал поездку: «{text}».\nДоступные линзы:\n{menu}\n"
              "Верни JSON: {\"lenses\": [id подходящих линз], \"month\": номер месяца или null, "
              "\"not_yet\": [чего гость хочет, но в списке линз нет — 1–3 слова по-русски, в именительном падеже]}. "
              "Только JSON.")
    body = {"model": LLM_MODEL, "temperature": 0, "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(f"{LLM_BASE_URL.rstrip('/')}/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "Authorization": f"Bearer {LLM_API_KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            content = json.load(r)["choices"][0]["message"]["content"]
        d = json.loads(re.search(r"\{.*\}", content, re.S).group(0))
        month = d.get("month")
        return {"lenses": [i for i in d.get("lenses", []) if i in BY_ID],
                "month": month if isinstance(month, int) and 1 <= month <= 12 else None,
                "not_yet": [str(x) for x in d.get("not_yet", [])][:3], "by": "llm"}
    except Exception as e:  # сеть, ключ, кривой JSON — откатываемся на правила
        log.warning("describe: LLM недоступна (%s), разбираю правилами", e)
        return None
