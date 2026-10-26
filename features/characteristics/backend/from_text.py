"""«Описать текстом»: фраза → спецификация новой характеристики. Сохраняется только после подтверждения.

Без ключа LLM — правила:
  «рядом / в N метрах / нет ли рядом + место» → поиск на карте (словарь osm_dict.json: слова → теги OSM);
  «нет ли рядом», «без», «подальше от» → хорошо, когда далеко (стройка, ЛЭП, промзона);
  «есть ли в номере / в отеле …» → отметки отеля на карте → ответы отеля → сайт → вопрос отелю.
С ключом — LLM получает реестр инструментов и теги, которые есть на карте Сочи, и возвращает спеку.
Спека в любом случае проходит проверку (spec.validate): несуществующий инструмент или тег не пройдут.
LLM собирает только план поиска; сами факты потом дают инструменты.
"""
import json
import logging
import math
import re
import urllib.request
from functools import lru_cache
from pathlib import Path

from core.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from core.textmatch import best, meaning_key

from .geo import known_tags
from .spec import GROUPS, ICONS, human, validate
from .tools import registry

log = logging.getLogger(__name__)
DICT = Path(__file__).resolve().parents[1] / "osm_dict.json"

FAR = r"нет ли|не было|\bбез\b|далеко от|подальше|не рядом|не хочу|не люблю|мешает|мешать|шумн"
NEAR = r"рядом|поблизости|недалеко|неподалеку|близко|пешком|в шаговой|в \d+\s*(м|метр|мин|км)|вокруг|по соседству"
IN_HOTEL = r"в номер|в отел|в здани|на территори|у отеля|есть ли у вас|в комнат|в апартамент|при отеле"
# что отель сам отмечает о себе на карте (data/seed/hotel_tags.json)
HOTEL_TAGS = [
    {"id": "wifi", "key": "internet_access", "yes": ["wlan", "yes", "wifi", "wired", "terminal"], "no": ["no"],
     "synonyms": ["wifi", "wi-fi", "вайфай", "вай фай", "интернет"]},
    {"id": "wheelchair", "key": "wheelchair", "yes": ["yes", "designated"], "no": ["no", "limited"],
     "synonyms": ["инвалидная коляска", "доступная среда", "пандус", "маломобильный", "инвалид", "коляска"]},
    {"id": "smoking", "key": "smoking", "yes": ["yes", "outside", "separated", "isolated", "dedicated"], "no": ["no"],
     "synonyms": ["курить", "курение", "для курящих", "покурить"]},
    {"id": "ac", "key": "air_conditioning", "yes": ["yes"], "no": ["no"], "synonyms": ["кондиционер", "кондей"]},
    {"id": "cards", "key": "payment:credit_cards", "yes": ["yes"], "no": ["no"],
     "synonyms": ["оплата картой", "платить картой", "банковская карта"]},
]
TRANSLIT = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
                    ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s",
                     "t", "u", "f", "h", "c", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))


@lru_cache(maxsize=1)
def osm_dict() -> list[dict]:
    return json.load(open(DICT, encoding="utf-8"))


def slug(text: str) -> str:
    s = "".join(TRANSLIT.get(c, c) for c in text.lower())
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:32] or "q"


def draft(text: str, existing: list[dict]) -> dict:
    """{spec, plan: [по-человечески], errors, warnings, by, exists?}. Ничего не сохраняет."""
    text = text.strip()
    found = _existing(text, existing)
    if found:
        return {"exists": {"id": found["id"], "title": found["title"]}, "by": "rules", "text": text}
    spec, by, notes = None, "rules", []
    if LLM_API_KEY and LLM_BASE_URL:
        spec = _llm(text)
        if spec:
            by = "llm"
            _, errors, _ = validate(dict(spec), {s["id"] for s in existing})
            if errors:   # LLM ошиблась в плане — откатываемся на правила, но честно говорим
                log.warning("from-text: спека от LLM не прошла проверку: %s", errors)
                notes.append("Модель собрала план с ошибкой — разобрали правилами")
                spec, by = None, "rules"
    if spec is None:
        spec = _rules(text)
    spec["text"] = text
    spec["origin"] = by
    taken = {s["id"] for s in existing}
    base, n = spec["id"], 2
    while spec["id"] in taken:
        spec["id"], n = f"{base}_{n}", n + 1
    s, errors, warnings = validate(spec, taken)
    return {"spec": s, "plan": human(s), "errors": errors, "warnings": notes + warnings, "by": by, "text": text}


def _existing(text, existing):
    """Фраза про то, что уже умеем («аптека рядом») — не плодим дубль, показываем готовое."""
    if re.search(FAR, text.lower()):
        return None
    hit = best(text, [s for s in existing if s.get("synonyms")])
    if not hit:
        return None
    s = next(s for s in existing if s["id"] == hit[0][0])
    # совпало одно слово из длинной фразы «есть ли в номере сейф и чайник» — это не про то
    meaningful = [w for w in meaning_key(text).split() if len(w) > 2 and w not in ("рядом", "есть", "ли", "отель")]
    return s if hit[0][1] >= max(1, len(meaningful) - 1) else None


def _minutes(t: str) -> int | None:
    m = re.search(r"(\d+)\s*(км|километр)", t)
    if m:
        return math.ceil(int(m.group(1)) * 1000 * 1.3 / 75)
    m = re.search(r"(\d+)\s*(м\b|метр)", t)
    if m:
        return max(1, math.ceil(int(m.group(1)) * 1.3 / 75))
    m = re.search(r"(\d+)\s*мин", t)
    return int(m.group(1)) if m else None


def _question(text):
    q = text.strip().rstrip("?.! ")
    return q[:1].upper() + q[1:] + "?"


def _rules(text: str) -> dict:
    t = text.lower().replace("ё", "е")
    far = bool(re.search(FAR, t))
    in_hotel = bool(re.search(IN_HOTEL, t)) and not re.search(r"рядом с отел|от отел|возле отел|около отел", t)
    place = best(text, osm_dict())
    tag = best(text, HOTEL_TAGS)
    if place and not in_hotel:
        return _near_spec(text, next(e for e in osm_dict() if e["id"] == place[0][0]), far, _minutes(t))
    hotel_tag = next(e for e in HOTEL_TAGS if e["id"] == tag[0][0]) if tag else None
    return _yes_no_spec(text, hotel_tag, near=bool(re.search(NEAR, t)))


def _near_spec(text, e, far, minutes):
    match_min, partial_min = e["match_min"], e["partial_min"]
    if minutes:
        match_min, partial_min = minutes, max(minutes + 2, round(minutes * 1.5))
    on_map = sum(known_tags().get(tg, 0) for tg in e["osm"])
    title = (e.get("far_title") or f"Без: {e['kind'].lower()}") if far else f"{e['kind']} рядом"
    question = _question(text)
    plan = [{"tool": "poi_nearby", "params": {"osm": e["osm"], "kind": e["kind"], "match_min": match_min,
                                              "partial_min": partial_min}}]
    if not on_map:   # на карте такого нет совсем — агент сам добавляет другие источники
        plan += [{"tool": "hotel_answers", "params": {"question": question}},
                 {"tool": "ask_hotelier", "params": {"question": f"Есть ли рядом с отелем: {e['kind'].lower()}? "
                                                                 "Сколько идти пешком?"}}]
    return {"id": e["id"] + ("_far" if far else ""), "title": title, "question": question, "kind": "near",
            "prefer": "far" if far else "near", "icon": e["icon"], "group": e["group"],
            "synonyms": e["synonyms"], "far_title": e.get("far_title"), "plan": plan,
            "min_confidence": 0.45, "ttl_days": 180}


def _yes_no_spec(text, hotel_tag, near):
    question = _question(text)
    title = _title(text)
    plan = []
    if hotel_tag:
        plan.append({"tool": "hotel_osm", "params": {"key": hotel_tag["key"], "yes": hotel_tag["yes"],
                                                     "no": hotel_tag["no"]}})
    plan += [{"tool": "hotel_answers", "params": {"question": question}},
             {"tool": "web_text", "params": {"question": question}},
             {"tool": "ask_hotelier", "params": {"question": question}}]
    spec = {"id": hotel_tag["id"] if hotel_tag else slug(title), "title": title, "question": question,
            "kind": "yes_no", "icon": "question", "group": "Прочее",
            "synonyms": (hotel_tag or {}).get("synonyms", []) + [title.lower()],
            "yes_text": f"{title}: да", "no_text": f"{title}: нет", "plan": plan, "min_confidence": 0.6,
            "ttl_days": 180, "ask_hotelier": question}
    if near and not hotel_tag:
        spec["note"] = "Такого места нет в словаре карты — без ключа LLM спросим у отелей"
    return spec


def _title(text):
    """«Есть ли в номере сейф?» → «Сейф в номере»: убрать вопросительные слова, место — в конец."""
    t = re.sub(r"^(а |и )?(есть ли|есть|имеется ли|можно ли|бывает ли|найдется ли|будет ли)\s+", "",
               text.strip().rstrip("?.! "), flags=re.I)
    m = re.match(r"^((?:в|на|у|при)\s+\S+)\s+(.+)$", t, flags=re.I)
    if m:
        t = f"{m.group(2)} {m.group(1)}"
    return (t[:1].upper() + t[1:])[:60]


# --- с ключом: план собирает LLM --------------------------------------------------------------------------

def _llm(text: str) -> dict | None:
    tools = "\n".join(f"- {t['id']} ({t['title']}): {t['about']} Параметры: {json.dumps(t['params'], ensure_ascii=False)}"
                      + ("" if t["available"] else " [ПОКА НЕ ПОДКЛЮЧЁН]") for t in registry())
    tags = ", ".join(f"{k} ({n})" for k, n in sorted(known_tags().items(), key=lambda x: -x[1]) if n >= 3)
    hotel = ", ".join(f"{e['key']}" for e in HOTEL_TAGS)
    example = {"id": "cycleway", "title": "Велодорожка рядом", "question": "Есть ли рядом велодорожки?",
               "kind": "near", "prefer": "near", "icon": "bike", "group": "Отдых",
               "synonyms": ["велодорожка", "покататься на велосипеде"],
               "plan": [{"tool": "poi_nearby", "params": {"osm": ["highway=cycleway", "bicycle=designated"],
                                                          "kind": "Велодорожка", "match_min": 7, "partial_min": 15}}],
               "min_confidence": 0.45, "ttl_days": 180}
    prompt = (
        "Ты собираешь план исследования новой характеристики отеля для сервиса подбора отелей в Сочи. "
        "Ты НЕ отвечаешь на вопрос и не придумываешь факты: ты выбираешь инструменты, которые найдут ответ "
        "в данных, по порядку от надёжного к запасному.\n"
        f"Описание от пользователя: «{text}»\n\n"
        f"Инструменты:\n{tools}\n\n"
        f"Теги OSM, которые есть на карте вокруг отелей (в скобках — число точек): {tags}\n"
        f"Теги самого отеля для hotel_osm: {hotel}\n"
        f"Иконки: {', '.join(sorted(ICONS))}. Группы: {', '.join(GROUPS)}.\n\n"
        "Правила: kind = near, если вопрос про место рядом с отелем (тогда первый шаг poi_nearby с тегами "
        "ТОЛЬКО из списка выше; prefer=far, если гостю хорошо, когда это далеко: стройка, ЛЭП, клуб); "
        "kind = yes_no, если вопрос про сам отель или номер (hotel_osm, если есть подходящий тег отеля, затем "
        "hotel_answers, web_text, последним ask_hotelier). Если на карте нужного нет — добавь hotel_answers и "
        "ask_hotelier после poi_nearby. id — латиница snake_case. title — 2–4 слова по-русски для фильтра. "
        "synonyms — 3–8 слов и фраз, которыми гость скажет это же. question — вопрос гостя, ask_hotelier — "
        "вопрос отелю на «вы». min_confidence 0.45 для near, 0.6 для yes_no.\n"
        f"Пример ответа: {json.dumps(example, ensure_ascii=False)}\n"
        "Верни только JSON спеки, без пояснений.")
    body = {"model": LLM_MODEL, "temperature": 0, "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(f"{LLM_BASE_URL.rstrip('/')}/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "Authorization": f"Bearer {LLM_API_KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            content = json.load(r)["choices"][0]["message"]["content"]
        return json.loads(re.search(r"\{.*\}", content, re.S).group(0))
    except Exception as e:  # сеть, ключ, кривой JSON — откатываемся на правила
        log.warning("from-text: LLM недоступна (%s), разбираю правилами", e)
        return None
