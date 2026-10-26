"""Факты с сайтов отелей с дословной цитатой: data/seed/web_chunks.json.gz → data/seed/facts_web.json.

Запуск: .venv/bin/python features/web_sources/pipeline/extract.py [--llm] [--only w51764141]

Без ключа — правила: в предложении с сайта ищем прямую формулировку («проживание с питомцами
возможно… до 15 кг», «расчётный час 12:00»). С ключом (--llm) — модель читает найденные поиском
куски сайта и отвечает строго по ним; ответ принимаем, только если её цитата дословно есть в тексте.
Факт = цитата + ссылка на страницу, а не догадка. Слова гостей (отзывы на сайте) и вопросы
из FAQ сайта фактами не считаем.
"""
import argparse
import datetime as dt
import gzip
import json
import os
import hashlib
import re
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
# ключ LLM для офлайн-прогона — из .env в корне репо (в Docker его передаёт compose)
for _line in (ROOT / ".env").read_text(encoding="utf-8").splitlines() if (ROOT / ".env").exists() else []:
    if "=" in _line and not _line.lstrip().startswith("#"):
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip().strip('"'))
from core import llm  # noqa: E402
from features.web_sources.backend.quote import prompt, source_of  # noqa: E402
from features.web_sources.backend.search import search  # noqa: E402
from features.web_sources.topics import TOPICS  # noqa: E402

SEED, CACHE = ROOT / "data/seed", ROOT / "data/raw/web/_llm_cache.json"
TTL_DAYS = 90
METHOD = "web-rules@0.1"

# голос гостя: «отдыхали», «порадовало», «спасибо персоналу», смайлы — это отзыв, а не слова отеля
GUEST = re.compile(r"\b(я|мы|нам|мне|нас)\b.{0,40}\b(жил|отдыха|был[иа]?|останавлив|приехал|понравил|заселил)|"
                   r"понравил|порадовал|спасибо|\bжил[иа]?\b|рекомендую|отзыв|отдыхали|проживал[иа]?\b|\){2,}|!{2,}|"
                   r"\b(минус|плюс)ы?\b|персонал\w* (вежлив|приветлив)|не смотря на|несмотря на хорош|вот только|"
                   r"\b\w{2,}(али|или|ыли)\b|не ?маловажно|хорош\w* (шумо|звуко)изоляц|[\U0001F300-\U0001FAFF\u2600-\u27BF]", re.I)
# не про сам отель: «в 200 м от отеля платная парковка», «рядом пляж с бассейном»
AROUND = re.compile(r"близост|рядом|неподал[её]к|в шаговой|возле|вокруг|достопримеч|в \d+ ?(м|метр\w*|км) от отеля", re.I)
NUM = r"(\d[\d\s ]{0,6}\d|\d)"


def num(s):
    return int(re.sub(r"\D", "", s))


def time_of(s):
    m = re.search(r"\b([01]?\d|2[0-4])[:.]([0-5]\d)\b", s)
    return f"{int(m.group(1)) % 24:02d}:{m.group(2)}" if m else None


def sentences(text: str):
    for line in text.split("\n"):
        for s in re.split(r"(?<=[.!?;])\s+(?=[А-ЯЁA-Z0-9«\"•\-–])", line):
            s = s.strip(" •-–—*\t")
            if 12 <= len(s) <= 400:
                yield s


# --- правила: (тема, регулярка, функция значения по предложению, уверенность) ---------------------

def _pets(s, m):
    neg = re.search(r"не (допуска|разреша|принима|предусмотр|размеща)|запрещ|невозможн|без (домашних )?(животн|питом)", s, re.I)
    if re.search(r"дики\w+ животн|решени\w* о возможност", s, re.I):
        return None   # «решение о размещении с животными принимает владелец» — это не «да»
    v = {"dogs": "нет" if neg else "да", "cats": "нет" if neg else "да"}
    if not neg:
        kg = re.search(r"(до|не более|не больше)\s*(\d{1,2})\s*кг", s)
        rub = re.search(NUM + r"\s*(руб|₽|р\.)", s)
        if kg:
            v["max_kg"] = int(kg.group(2))
        if rub and re.search(r"сутк|ноч|день|дополнит|доплат|стоимост", s, re.I):
            v["fee_rub"] = num(rub.group(1))
    return v




def _checkin(s, m):
    if re.search(r"интервал|%|стоимост|оплат|ранн\w+ заезд|поздн\w+ выезд", s, re.I) or len(s) > 160:
        return None   # правила отмены и доплат, а не время заезда
    v = {}
    a = re.search(r"(заезд|заселени|check.?in)\w*\s*(—|-|:|с|после|в|от)?\s*(\d{1,2}[:.]\d\d)", s, re.I)
    b = re.search(r"(выезд|выселени|расч[её]тн\w* час|check.?out)\w*\s*(—|-|:|до|в)?\s*(\d{1,2}[:.]\d\d)", s, re.I)
    if a and not re.search(r"ранн", s[:a.start() + 12], re.I):
        v["checkin"] = time_of(a.group(3))
    if b and not re.search(r"поздн", s[:b.start() + 12], re.I):
        v["checkout"] = time_of(b.group(3))
    return v or None


def _parking(s, m):
    if AROUND.search(s) or re.search(r"парков\w* (зон|аллея)|паркову|поиск\w* парков|найти\w* .{0,15}парков", s, re.I):
        return None
    if re.search(r"нет (своей |собственной )?парков|парковк\w* (нет|отсутств)|без парковки", s, re.I):
        return {"parking": "нет"}
    v = {"parking": "есть"}
    if re.search(r"бесплатн", s, re.I):
        v["price_rub"] = 0
    else:
        r = re.search(NUM + r"\s*(руб|₽)", s)
        if r:
            v["price_rub"] = num(r.group(1))
    return v


def _breakfast(s, m):
    if re.search(r"без завтрак", s, re.I):
        return None
    incl = re.search(r"включ|входит|\+ ?завтрак", s, re.I) and not re.search(r"тариф|можно выбрать|на выбор", s, re.I)
    v = {"breakfast": "включён" if incl else "есть"}
    if re.search(r"шведск", s, re.I):
        v["kind"] = "шведский стол"
    elif re.search(r"меню|a la carte|порционн", s, re.I):
        v["kind"] = "меню"
    return v


def _crib(s, m):
    if re.search(r"не (предоставля|предусмотр)\w* .{0,20}кроватк|кроватк\w* .{0,40}(нет|не предоставля|не предусмотр)", s, re.I):
        return {"crib": "нет"}
    v = {"crib": "бесплатно" if re.search(r"бесплатн", s, re.I) else
         "за доплату" if re.search(r"доплат|дополнительн\w* плат|руб|₽", s, re.I) else "есть"}
    if re.search(r"по (предварительн\w* )?запрос|заранее|при бронир", s, re.I):
        v["preorder"] = "нужно"
    return v


ALL_ROOMS = r"(в|во|у) (кажд|всех)\w* (номер|апартамент)|все\w* (номер|апартамент)\w* (отеля )?(оборудован|оснащен|имеют|с)|кажд\w+ номер"


def _ac(s, m):
    if re.search(r"для волос|бальзам", s, re.I):
        return None
    return {"ac": "во всех номерах" if re.search(ALL_ROOMS, s, re.I) else "есть"}


def _balcony(s, m):
    if re.search(r"без балкон", s, re.I):
        return None
    if re.search(r"\bнет балкон|балкон\w* (нет|отсутству)", s, re.I):
        return {"balcony": "нет"}
    every = re.search(ALL_ROOMS, s, re.I) and not re.search(r"не (во|в|у) все|не кажд", s, re.I)
    return {"balcony": "во всех номерах" if every else "в части номеров"}


def _transfer(s, m):
    if not re.search(r"аэропорт|вокзал", s, re.I):
        return None
    v = {"from": "аэропорт" if re.search(r"аэропорт", s, re.I) else "вокзал","transfer": "бесплатно" if re.search(r"бесплатн", s, re.I) else
         "за доплату" if re.search(r"доплат|руб|₽|платн|стоимост|заказ", s, re.I) else "есть"}
    r = re.search(NUM + r"\s*(руб|₽)", s)
    if r:
        v["price_rub"] = num(r.group(1))
    return v


def _noise_rules(s, m):
    t = re.search(r"тишин\w*\s*(с|после)\s*(\d{1,2}[:.]\d\d|\d{1,2})", s, re.I)
    if not t:
        return None
    q = time_of(t.group(2)) or f"{int(t.group(2)):02d}:00"
    v = {"quiet_from": q}
    if re.search(r"вечеринк\w* .{0,20}(запрещ|не допуска)|запрещ\w* .{0,30}вечеринк", s, re.I):
        v["parties"] = "нельзя"
    return v


def _quiet_rooms(s, m):
    return {"noise": "не слышно" if re.search(r"не слышн|тишин", s, re.I) else "шумоизоляция", "quiet": "шумоизоляция"}


def _sea_view(s, m):
    if re.search(r"\bнет\b.{0,10}вид|без вида", s, re.I):
        return None
    if not re.search(r"номер|апартамент|студи|люкс|стандарт|делюкс|сюит|балкон|лоджи|окн|спальн", s, re.I):
        return None   # «терраса ресторана с видом на море» — не про номера
    allr = re.search(r"(все|кажд\w+|любого)\s+(номер|апартамент)\w*|(из|со|с) всех (номер|апартамент|окон)", s, re.I)
    return {"rooms": "все номера" if allr else "часть номеров", "panoramic": bool(re.search(r"панорам", s, re.I))}


def _beach_claim(s, m):
    a = re.search(r"(\d{1,3})\s*(минут|мин\b)\w*\s*(пешком|ходьбы|пешей прогулки)?\s*(до|от)\s*(моря|пляжа|набережн)", s, re.I)
    b = re.search(r"(\d{2,4})\s*(м|метр\w*)\s*(до|от)\s*(моря|пляжа|берега)", s, re.I)
    c = re.search(r"в\s*(\d{2,4})\s*(м|метр\w*)\s*от\s*(моря|пляжа|берега)", s, re.I)
    v = {}
    if a:
        v["walk_min"] = int(a.group(1))
    if b or c:
        v["meters"] = int((b or c).group(1))
    if re.search(r"на (первой|1-?й) (береговой )?линии|на берегу моря", s, re.I):
        v["first_line"] = True
    return v or None


def _own_beach(s, m):
    if AROUND.search(s) or re.search(r"трансфер|шатл", s, re.I) and not re.search(r"собствен|сво[йего]", s, re.I):
        return None
    return {"own_beach": "есть"}


def _pool(s, m):
    if AROUND.search(s):
        return None
    v = {"pool": "есть"}
    if re.search(r"подогрев", s, re.I) and not re.search(r"без подогрев", s, re.I):
        v["heated"] = True
    if re.search(r"(?<!от)крыт\w*\s+(подогрева\w+\s+)?бассейн", s, re.I):
        v["kind"] = "крытый"
    elif re.search(r"открыт\w*\s+(подогрева\w+\s+)?бассейн|бассейн\w* под открытым|на улиц", s, re.I):
        v["kind"] = "открытый"
    return v


def _kitchen(s, m):
    return {"kitchen": "во всех номерах" if re.search(r"(в|во) (кажд|всех)\w* (номер|апартамент)", s, re.I) else "в части номеров"}


def _wifi(s, m):
    return {"wifi": "бесплатно" if re.search(r"бесплатн", s, re.I) else "есть"}


def _lift(s, m):
    if re.search(r"лифтинг", s, re.I):
        return None
    if re.search(r"нет лифт|без лифт|лифт\w* нет|лифт\w* отсутств", s, re.I):
        return {"lift": "нет"}
    return {"lift": "есть"}


RULES = [
    ("pets", r"(проживани|размещени|заселени|приезд|отдых)\w*\s+с\s+(домашн\w+\s+)?(животн|питом|собак)\w*\s+(возможн|разреш|допуска|не допуска|запрещ|не разреш|не предусмотр|невозможн)"
             r"|(возможн\w*|разреш\w*|допуска\w*)\s+(проживани|размещени)\w*\s+с\s+(домашн\w+\s+)?(животн|питом)"
             r"|принима\w*\s+(гостей\s+)?(с\s+детьми\s+и\s+)?с?\s*(домашн\w+\s+)?(животн|питом)\w*"
             r"|можно с (животн|питом|собак)|pet.?friendly|(животн|питомц)\w* не (допуска|принима)"
             r"|доплат\w* за (проживани|размещени)\w* (с )?(домашн\w+ )?(животн|питом)", _pets, 0.7),
    ("checkin", r"(заезд|заселени|check.?in)\w*\s*(—|-|:|с|после|в|от)?\s*\d{1,2}[:.]\d\d|"
                r"(выезд|выселени|расч[её]тн\w* час|check.?out)\w*\s*(—|-|:|до|в)?\s*\d{1,2}[:.]\d\d", _checkin, 0.75),
    ("parking", r"(бесплатн|собственн|сво[яей]|охраняем|закрыт|платн|подземн|крыт|огороженн)\w*\s+(парковк|паркинг|автостоянк|стоянк)"
                r"|(парковк|паркинг|автостоянк)\w*\s+(на территории|для гостей|для автомобил)|есть (своя )?парковк|"
                r"парковк\w* (включает|на \d+)|нет (своей |собственной )?парковк", _parking, 0.7),
    ("breakfast", r"завтрак\w*\s+(включ|входит|шведск|подаю|в формате|сервиру|с \d)|(шведск\w+ стол\w*)\s*.{0,20}завтрак|"
                  r"тариф\w* с завтрак|проживание\s*\+\s*завтрак|предлага\w+ .{0,30}завтрак|завтрак\w* .{0,30}(руб|₽)", _breakfast, 0.7),
    ("crib", r"(детск\w+\s+)?кроватк\w*|манеж", _crib, 0.7),
    ("ac", r"кондиционер|сплит-систем|климат-контрол", _ac, 0.6),
    ("balcony", r"(номер|студи|люкс|апартамент)\w*\s.{0,30}\s(балкон|лоджи)|(с|из)\s+(балкон|лоджи)\w*|балкон\w* с ", _balcony, 0.6),
    ("transfer", r"трансфер\w*", _transfer, 0.7),
    ("noise_rules", r"тишин\w*\s*(с|после)\s*\d", _noise_rules, 0.75),
    ("quiet_rooms", r"шумоизол|звукоизол|шумозащит|шумоподавл", _quiet_rooms, 0.5),
    ("sea_view", r"(вид\w*|видом)\s+на\s+(море|черное море|чёрное море)", _sea_view, 0.6),
    ("beach_claim", r"\d\s*(минут|мин\b)\w*\s*(пешком |ходьбы |пешей прогулки )?(до|от)\s*(моря|пляжа|набережн)|"
                    r"\d{2,4}\s*(м|метр\w*)\s*(до|от)\s*(моря|пляжа|берега)|на (первой|1-?й) (береговой )?линии", _beach_claim, 0.6),
    ("own_beach", r"(собственн|сво[йего]|частн)\w*\s+(оборудованн\w+ )?(галечн\w+ |песчан\w+ )?пляж|пляж\w* отеля", _own_beach, 0.6),
    ("pool", r"(открыт|крыт|подогрева|панорамн|с подогревом|летн|детск)\w*\s+бассейн|бассейн\w*\s+(с подогревом|под открытым|на территории|на крыше)|"
             r"\d\s+бассейн", _pool, 0.7),
    ("kitchen", r"(с|со)\s+(мини-?)?кухн|кухонн\w+\s+(зон|угол)|оборудованн\w+\s+кухн|кухн\w*-(столов|гостин)", _kitchen, 0.6),
    ("wifi", r"(бесплатн\w+\s+)?(wi-?fi|вай-?фай|беспроводн\w+ интернет)", _wifi, 0.6),
    ("lift", r"(есть|гостев\w+|пассажирск\w+|удобн\w+|отдельн\w+|\d)\s+лифт|лифт\w* (ходит|есть|нет|до)|на лифте|нет лифт", _lift, 0.7),
]
RULES = [(t, re.compile(p, re.I), fn, c) for t, p, fn, c in RULES]


def rules_for(chunks: list[dict]) -> dict[str, dict]:
    """Лучшее найденное правилами по каждой теме: {topic: {value, quote, url, confidence}}."""
    best = {}
    for c in chunks:
        if c.get("reviews"):
            continue
        for s in sentences(c["text"]):
            if s.endswith("?") or GUEST.search(s):
                continue
            for tid, rx, fn, conf in RULES:
                m = rx.search(s)
                if not m:
                    continue
                v = fn(s, m)
                if not v:
                    continue
                prev = best.get(tid)
                # полнее значение — лучше; при равенстве — фраза, а не подпись к иконке
                # подпись-иконка с сайта («Можно с животными») хуже связной фразы, но и простыня не нужна
                rank = (len(v), 30 <= len(s) <= 250, -len(s))
                if prev and prev["rank"] >= rank:
                    continue
                best[tid] = {"value": v, "quote": s, "url": c["url"], "fetched_at": c["fetched_at"],
                             "confidence": conf if len(s) < 300 else conf - 0.1, "rank": rank, "method": METHOD}
    return best


# --- LLM: ответ строго по тексту сайта с дословной цитатой ---------------------------------------
# Ответ модели принимаем, только если: цитата дословно есть в найденном куске сайта (quote.source_of),
# цитата про тему вопроса, это не слова гостя и не вопрос из FAQ, значение укладывается в поля темы
# и не спорит с тем, что правило видит в той же цитате. Иначе — отбрасываем и считаем, почему.

# цитата должна быть про тему: «Есть ли в номере стиральная машина? Нет.» — не ответ про кухню
STEM = {"pets": r"животн|питом|собак|кош|pet", "checkin": r"заезд|засел|выезд|высел|расч[её]тн|check",
        "parking": r"парков|паркинг|стоянк", "breakfast": r"завтрак", "crib": r"кроват|манеж",
        "ac": r"кондиц|сплит|климат", "balcony": r"балкон|лодж", "transfer": r"трансфер",
        "noise_rules": r"тишин|шум|вечерин", "quiet_rooms": r"шумо|звуко|тишин|не слышн",
        "sea_view": r"вид\w* на .{0,15}мор|панорам\w* .{0,20}мор", "beach_claim": r"мор|пляж|берег|набережн",
        "own_beach": r"пляж", "pool": r"бассейн", "kitchen": r"кухн", "wifi": r"wi-?fi|вай-?фай|интернет", "lift": r"лифт"}
STEM = {k: re.compile(v, re.I) for k, v in STEM.items()}
NEG = {"нет"}
EVERY = re.compile(ALL_ROOMS + r"|(из|со|с|во|в) (всех|любого|каждого) (номер|апартамент|окон|окна|комнат)", re.I)
NEAR_TOPICS = {"parking", "pool", "own_beach"}
NEG_WORD = re.compile(r"\bнет\b|\bне\s|\bбез\b|запрещ|отсутств|невозможн|no\b", re.I)
FREE = re.compile(r"бесплатн|не взима|без доплат|без дополнительн|free|включ|входит в стоимост", re.I)
BY_ID = {t["id"]: t for t in TOPICS}
RULE_OF = {tid: (rx, fn) for tid, rx, fn, _ in RULES}


def clean_value(tid: str, value: dict) -> dict:
    """Значение модели → только поля темы и допустимые варианты («до 15 кг» → 15, «15:00» → «15:00»)."""
    out = {}
    for f in BY_ID[tid]["fields"]:
        v = value.get(f["id"])
        if v in (None, "", []):
            continue
        typ = f["type"]
        if f.get("options"):
            if isinstance(v, bool) and "да" in f["options"]:
                v = "да" if v else "нет"
            v = str(v).strip().lower().replace("включен", "включён")
            if v in f["options"]:
                out[f["id"]] = v
        elif typ.startswith("number"):
            m = re.search(r"\d[\d\s ]*", str(v))
            if m and not isinstance(v, bool):
                out[f["id"]] = int(re.sub(r"\D", "", m.group(0)))
        elif typ.startswith("time"):
            t = time_of(str(v))
            if t:
                out[f["id"]] = t
        elif typ == "bool" and isinstance(v, bool):
            out[f["id"]] = v
    return out


def judge(tid: str, r: dict | None, chunks: list[dict]) -> tuple[str, dict | None]:
    """Разбор ответа модели: (исход, принятый ответ). Исходы — для сравнения режимов."""
    if not r or not r.get("found"):
        return "not_found", None
    quote = str(r.get("quote") or "").strip()
    if not quote:
        return "no_quote", None
    src = source_of(quote, chunks)
    if not src:
        return "quote_not_in_text", None           # главное правило: цитаты нет на сайте дословно
    if src.get("reviews") or quote.endswith("?") or GUEST.search(quote):
        return "guest_or_faq", None
    if not STEM[tid].search(quote) or (tid in NEAR_TOPICS and AROUND.search(quote)):
        return "off_topic", None                     # «рядом можно найти парковку» — не про сам отель
    value = clean_value(tid, r.get("value") if isinstance(r.get("value"), dict) else {})
    if not value:
        return "bad_value", None
    # каждое число ответа должно быть в цитате: «тишина с 23:00» при цитате без времени — додумано
    digits = set(re.findall(r"\d+", re.sub(r"(?<=\d)[\s ](?=\d{3})", "", quote)))
    def stated(v):
        if isinstance(v, bool) or not re.search(r"\d", str(v)):
            return True
        return all(d.lstrip("0") in {x.lstrip("0") for x in digits} for d in re.findall(r"\d+", str(v)))
    value = {k: v for k, v in value.items() if stated(v)}
    if not value:
        return "number_not_in_quote", None
    key = BY_ID[tid]["fields"][0]["id"]
    if value.get(key) in NEG and not NEG_WORD.search(quote):
        return "inferred_no", None                   # «нет» должно быть сказано, а не выведено из молчания
    if not EVERY.search(quote):                      # «во всех номерах» — только если так и написано
        value = {k: {"все номера": "часть номеров", "во всех номерах": "в части номеров"}.get(v, v) for k, v in value.items()}
    if not FREE.search(quote):                       # «бесплатно», а в цитате об этом ни слова — убираем
        opts = {f["id"]: f.get("options") or [] for f in BY_ID[tid]["fields"]}
        value = {k: ("есть" if v == "бесплатно" else v) for k, v in value.items()
                 if not (k == "price_rub" and v == 0) and not (v == "бесплатно" and "есть" not in opts[k])}
        if not value:
            return "bad_value", None
    rx, fn = RULE_OF[tid]
    m = rx.search(quote)
    ruled = fn(quote, m) if m else None
    if ruled and key in ruled and key in value and (ruled[key] in NEG) != (value[key] in NEG):
        return "contradicts_quote", None             # модель сказала «да», а в цитате «нельзя»
    try:
        BY_ID[tid]["text"](value)
    except Exception:  # noqa: BLE001 — после чисток не осталось главного поля («тишина с …» без времени)
        return "bad_value", None
    return "accepted", {"value": value, "quote": quote, "url": src["url"], "fetched_at": src["fetched_at"],
                        "confidence": 0.7, "method": f"web-llm@0.2:{llm.LLM_MODEL}"}


def llm_for(hotel_id: str, cache: dict, log: Counter) -> dict[str, dict]:
    out = {}
    for t in TOPICS:
        found = search(hotel_id, t["query"], k=4)
        if not found:
            continue
        p = prompt(t["question"], found, t["fields"])
        key = hashlib.sha1((llm.LLM_MODEL + p).encode()).hexdigest()
        if key not in cache:
            # «размышления» модели не нужны — ответ всё равно проверяем цитатой, а так в 10 раз быстрее
            r = llm.chat([{"role": "user", "content": p}], as_json=True, timeout=60, think=False)
            if r is None:                            # сеть/таймаут — не кэшируем, повторим в следующий раз
                log["llm_error"] += 1
                continue
            cache[key] = r
        verdict, ok = judge(t["id"], cache[key], found)
        log[verdict] += 1
        if ok:
            out[t["id"]] = ok
        elif verdict not in ("not_found",):
            REJECTED.append({"hotel_id": hotel_id, "topic": t["id"], "why": verdict, "answer": cache[key]})
    return out


REJECTED: list[dict] = []


def to_fact(hotel_id: str, tid: str, r: dict) -> dict:
    t = next(x for x in TOPICS if x["id"] == tid)
    got = dt.date.fromisoformat(r["fetched_at"][:10])
    return {
        "hotel_id": hotel_id, "scope": "hotel", "characteristic": f"web:{tid}",
        "value": {**r["value"], "text": t["text"](r["value"])},
        "confidence": round(r["confidence"], 2), "source": "web:" + urlparse(r["url"]).netloc.removeprefix("www."),
        "method_version": r["method"],
        "evidence": {"url": r["url"], "quote": r["quote"], "fetched_at": r["fetched_at"], "topic": tid},
        "obtained_at": got.isoformat(), "valid_until": (got + dt.timedelta(days=TTL_DAYS)).isoformat(),
        "status": "active",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="уточнить ответы моделью (нужен LLM_API_KEY)")
    ap.add_argument("--only", default="")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    with gzip.open(SEED / "web_chunks.json.gz", "rt", encoding="utf-8") as f:
        by = defaultdict(list)
        for c in json.load(f):
            by[c["hotel_id"]].append(c)
    if a.only:
        by = {k: v for k, v in by.items() if k in a.only.split(",")}
    use_llm = a.llm and llm.enabled()
    if a.llm and not use_llm:
        print("LLM_API_KEY/LLM_MODEL не заданы — только правила", file=sys.stderr)
    cache = json.load(open(CACHE, encoding="utf-8")) if use_llm and CACHE.exists() else {}
    cache = {k: v for k, v in cache.items() if v is not None}   # старые записи-ошибки переспросим
    rules = {hid: rules_for(cs) for hid, cs in sorted(by.items())}
    found = {hid: dict(r) for hid, r in rules.items()}
    log, by_llm = Counter(), {}
    if use_llm:
        try:
            with ThreadPoolExecutor(a.workers) as ex:
                by_llm = dict(zip(rules, ex.map(lambda h: llm_for(h, cache, log), rules)))
        finally:                          # ответы модели не теряем, даже если прогон упал
            json.dump(dict(cache), open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
        for hid, got in by_llm.items():
            found[hid].update(got)        # модель с проверенной цитатой точнее правил
    facts, per_topic = [], defaultdict(int)
    for hid, got in found.items():
        for tid, r in got.items():
            facts.append(to_fact(hid, tid, r))
            per_topic[tid] += 1
    if not a.only:
        json.dump(facts, open(SEED / "facts_web.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    hotels = len({f["hotel_id"] for f in facts})
    n_rules = sum(len(r) for r in rules.values())
    print(f"правила: фактов {n_rules} у {sum(1 for r in rules.values() if r)} отелей")
    print(f"итого: фактов {len(facts)} у {hotels} отелей, тем {len(per_topic)}: {dict(sorted(per_topic.items(), key=lambda x: -x[1]))}")
    if use_llm:
        both = [(h, t) for h in by_llm for t in by_llm[h] if t in rules[h]]
        same = sum(1 for h, t in both if by_llm[h][t]["quote"] == rules[h][t]["quote"]
                   or to_fact(h, t, by_llm[h][t])["value"]["text"] == to_fact(h, t, rules[h][t])["value"]["text"])
        new = sum(1 for h in by_llm for t in by_llm[h] if t not in rules[h])
        print(f"модель: {dict(log)}; приняли {sum(len(x) for x in by_llm.values())}, из них новых {new}, "
              f"там же, где правила, — {len(both)} (тот же ответ {same})")
        report = {"log": dict(log), "rejected": REJECTED,
                  "pairs": [{"hotel_id": h, "topic": t, "llm": by_llm[h].get(t), "rules": rules[h].get(t)}
                            for h in by_llm for t in set(by_llm[h]) | set(rules[h])]}
        json.dump(report, open(ROOT / "data/raw/web/_llm_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1,
                  default=str)
    if a.only:
        for f in facts:
            print(f"{f['characteristic']:<18} {f['method_version'][:10]:<10} {f['value']['text']:<40} «{f['evidence']['quote'][:150]}»")


if __name__ == "__main__":
    main()
