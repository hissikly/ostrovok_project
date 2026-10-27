"""«Не нашли, что искали?» под сравнением: фраза гостя → свои строки таблицы.

Фраза раскладывается на пункты, у каждого — свой источник; значения не придумываем:
- место («концерт в Фестивальном», «Зимний театр») — ищем по названию среди мест OSM и подборки
  «Что посмотреть», минуты — по пешеходному графу (core/walk.py), дальше 40 мин — оценка на машине;
- то, что уже умеет подбор (море, тишина, «что рядом»), — строки линз, как в основной таблице;
- то, что знает только отель (завтрак, питомцы…), — база знаний; про номер и отель своими словами
  («разные спальни») — поиск по текстам сайтов отелей с дословной цитатой, нет — «Спросить у отеля»;
- «бюджет», «подешевле» — строка цены.
Без ключа LLM фразу разбирают правила; с ключом модель только понимает фразу (что за место, какой вопрос
к отелю) — факты по-прежнему из карты и сайтов.
"""
import math
import re
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from core import llm
from core.seed import load
from core.textmatch import STOP, lemmas
from core.walk import route
from features.facts.backend import facts_for
from features.hotels.backend import hotel
from features.search.backend.describe import _askable, _catalog, RULES, describe
from features.search.backend.lenses import BY_ID, MATCH, NO, PARTIAL, UNKNOWN
from features.sights.backend import sights
from features.web_sources.backend import ask as web_ask

from .compare import _answer_cell, _winners, lens_row

VENUES = {"amenity=theatre", "amenity=arts_centre", "amenity=concert_hall", "amenity=events_venue", "amenity=cinema",
          "amenity=nightclub", "leisure=stadium", "leisure=sports_centre", "leisure=park", "leisure=water_park",
          "tourism=museum", "tourism=attraction", "tourism=zoo", "tourism=theme_park", "tourism=gallery"}
GENERIC = {"театр", "зал", "центр", "концертный", "дворец", "клуб", "кинотеатр", "музей", "спортивный", "культура",
           "культурный", "дом", "им", "имя", "сочи", "адлер", "парк", "сад", "галерея", "комплекс", "кино", "арена"}
WALK_MATCH, WALK_PARTIAL, WALK_MAX = 15, 30, 40          # как в «Что посмотреть»: рядом / можно дойти / на машине
CAR_DETOUR, CAR_KMH, CAR_PARK = 1.3, 40, 5
M_LAT, M_LON = 110_540, 111_320 * math.cos(math.radians(43.58))
PRICE = re.compile(r"бюджет|дешев|недорог|подешев|эконом|цен[аыу]|стоимост|деньг|копе[йе]|скромн")
# слова о самой поездке — не пожелание к отелю («еду с другом на концерт»)
TRIP = {"ехать", "поехать", "приехать", "еду", "едем", "друг", "подруга", "семья", "жена", "муж", "дети", "концерт",
        "отпуск", "отдых", "выходной", "командировка", "хотеть", "хотеться", "мочь", "нужно", "нужный", "очень", "ещё",
        "также", "тоже", "весь", "день", "неделя", "поездка", "сочи", "адлер", "город", "ограниченный", "ограничить",
        "хороший", "лучше", "главное", "важно", "вечер", "утро"}


# --- места -----------------------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _places() -> list[dict]:
    """Места, до которых можно посчитать путь: подборка «Что посмотреть» и площадки/парки/музеи из OSM."""
    out = [{"name": s["name"], "names": [s["name"], *s.get("synonyms", [])], "lat": s["lat"], "lon": s["lon"],
            "src": "sights"} for s in sights()]
    seen = {s["name"].lower() for s in out}
    for lat, lon, kind, name, *_ in (load("poi.json") or {}).get("items", []):
        if kind in VENUES and name and name.lower() not in seen:
            seen.add(name.lower())
            out.append({"name": name, "names": [name], "lat": lat, "lon": lon, "src": "osm"})
    for p in out:
        p["keys"] = [_key(n) for n in p["names"]]
    return out


def _key(name: str) -> tuple[set, set] | None:
    """(все значимые слова названия, отличительные) — «Концертный центр Сириус» → ({концертный, центр, сириус}, {сириус})."""
    ws = {w for w in lemmas(name) if w not in STOP and len(w) > 2}
    if not ws:
        return None
    return ws, {w for w in ws if w not in GENERIC and len(w) >= 5}


def find_places(text: str) -> list[dict]:
    """Места, названные во фразе: все отличительные слова названия есть во фразе (или все слова, если отличительных нет)."""
    t = set(lemmas(text))
    found = []
    for p in _places():
        for k in p["keys"]:
            if not k:
                continue
            ws, dist = k
            need = dist or (ws if len(ws) >= 2 else set())
            if need and need <= t:
                found.append((len(need), len(ws & t), p))
                break
    found.sort(key=lambda x: (-x[0], -x[1]))
    out, used = [], set()
    for n, _, p in found:   # «Зимний театр» не должен дать ещё и просто «театр» соседа
        k = frozenset(w for kk in p["keys"] if kk for w in (kk[1] or kk[0]))
        if k <= used:
            continue
        used |= k
        out.append(p)
    return out[:3]


def _place_cell(h: dict, p: dict) -> dict:
    r = route(h["lat"], h["lon"], p["lat"], p["lon"])
    if r and r["minutes"] <= WALK_MAX:
        m = r["minutes"]
        km = f"{r['meters']} м" if r["meters"] < 1000 else f"{r['meters'] / 1000:.1f} км".replace(".", ",")
        return {"state": MATCH if m <= WALK_MATCH else PARTIAL, "value": f"{m} мин пешком", "sub": km, "key": m,
                "source": "computed:osm-walk", "confidence": 0.8,
                "how": f"Посчитали пеший путь по карте OpenStreetMap до «{p['name']}» с подъёмами и спусками. Обратно — {r['back_minutes']} мин."}
    d = math.hypot((p["lat"] - h["lat"]) * M_LAT, (p["lon"] - h["lon"]) * M_LON)
    m = round(d * CAR_DETOUR / (CAR_KMH * 1000 / 60) + CAR_PARK)
    return {"state": NO, "value": f"≈ {m} мин на машине", "sub": "пешком больше 40 мин", "key": 100 + m,
            "source": "computed:straight-line", "confidence": 0.5,
            "how": f"Пешком до «{p['name']}» дольше 40 минут. На машине — оценка по прямой ×1,3, 40 км/ч и 5 минут на парковку."}


def _to(name: str) -> str:
    return f"До места «{name}»" if not re.search(r"[«\"„“]", name) else f"До места {name}"


# --- вопросы к отелю своими словами -------------------------------------------------------------------

def _clauses(text: str) -> list[str]:
    parts = re.split(r"[,.;!?]|\s(?:но|а|и|ещё|еще|плюс)\s", text)
    return [c.strip() for c in parts if c and c.strip()]


def _is_trip(clause: str) -> bool:
    ws = [w for w in lemmas(clause) if w not in STOP and len(w) > 1]
    return not ws or all(w in TRIP for w in ws)


def hotel_questions(text: str, places: list[dict]) -> list[str]:
    """Без ключа: части фразы, которые не легли ни в фильтры, ни в места, ни в цену, — вопрос к отелю."""
    out = []
    for c in _clauses(text):
        low = c.lower()
        if PRICE.search(low) or any(re.search(rx, low) for rx, _ in RULES) or _catalog(c) or _askable(c) \
                or find_places(c) or _is_trip(c):
            continue
        out.append(re.sub(r"^((хотим|хочу|хотелось бы|нужн[аоы]?|чтобы|чтоб|желательно|был[аои]?)\s+)+", "", c, flags=re.I))
    return out[:2]


def _hotel_cell(h: dict, q: str) -> dict:
    a = web_ask(h["id"], q)
    if not a:
        return {"state": UNKNOWN, "value": "Не знаем", "sub": "", "key": None, "ask_text": q,
                "how": "На сайте отеля про это ничего не нашли. Вопрос уйдёт отелю, обычно отвечают за 1–3 дня."}
    quote, text = a.get("quote") or "", a.get("text") or ""
    # с ключом модель отвечает коротко своими словами (только по цитате) — показываем ответ, цитату — в «как узнали»;
    # без ключа ответа нет — показываем само предложение с сайта
    sub = text if text and not text.startswith("На сайте отеля") else f"«{quote}»"
    return {"state": PARTIAL, "value": "Пишут на сайте", "sub": sub[:140] + ("…" if len(sub) > 140 else ""),
            "key": None, "source": a.get("source"), "confidence": a.get("confidence"), "url": a.get("url"),
            "how": f"На сайте отеля: «{quote}» ({a.get('url')}, {a.get('obtained_at')}). Цитату сверили с текстом сайта дословно."}


# --- разбор фразы ------------------------------------------------------------------------------------

def _llm_parse(text: str) -> dict | None:
    """С ключом: какие места названы и что гость хочет знать про сам отель/номер. Факты модель не даёт."""
    r = llm.chat([{"role": "user", "content": (
        f"Гость сравнивает отели в Сочи и написал: «{text}».\n"
        "Верни JSON: {\"places\": [названия конкретных мест в городе, куда гость собирается (концертный зал, театр, "
        "стадион, парк) — как написал гость], \"hotel\": [что гость хочет знать про сам отель или номер, чего не узнать "
        "по карте, — коротко, 2–6 слов, например «две отдельные спальни»; про море, пляж, тишину, кафе рядом и цену сюда "
        "не пиши], \"price\": true, если гостю важна цена или бюджет}. Только JSON.")}], as_json=True, think=False, timeout=20)
    if not isinstance(r, dict):
        return None
    return {"places": [str(x) for x in r.get("places") or []][:3], "hotel": [str(x) for x in r.get("hotel") or []][:2],
            "price": bool(r.get("price"))}


def custom_rows(ids: list[str], text: str, ctx: dict) -> dict:
    hs = [hotel(i) for i in ids]
    with ThreadPoolExecutor(max_workers=2) as pool:   # два вопроса модели — параллельно, без ключа оба мгновенно
        fd = pool.submit(describe, text)               # фильтры подбора и вопросы из базы знаний — как «✨ Опиши»
        fp = pool.submit(_llm_parse, text) if llm.enabled() else None
        d, parsed = fd.result(), fp.result() if fp else None
    by = "llm" if parsed else "rules"

    places = find_places(text)
    for name in (parsed or {}).get("places", []):
        places += [p for p in find_places(name) if p not in places]
    places = places[:3]
    questions = parsed["hotel"] if parsed else hotel_questions(text, places)
    price = parsed["price"] if parsed else bool(PRICE.search(text.lower()))

    rows = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for p in places:
            cells = list(pool.map(lambda h: _place_cell(h, p), hs))
            _winners(cells)
            rows.append({"id": f"place:{p['name']}", "title": _to(p["name"]), "icon": "pin", "cells": cells})

        lens_ids = [l for l in d["lenses"] if l in BY_ID]
        if lens_ids:
            facts = {h["id"]: facts_for(h["id"]) for h in hs}
            by_id = {h["id"]: {f["id"]: f for f in facts[h["id"]]} for h in hs}
            for l in lens_ids:
                rows.append(lens_row(l, hs, [BY_ID[l]["fn"](facts[h["id"]], ctx) for h in hs], by_id, ctx))
        for a in d.get("ask", []):
            cells = [_answer_cell(h["id"], a["topic"], ctx) for h in hs]
            _winners(cells)
            rows.append({"id": a["topic"], "title": a["question"].rstrip("?"), "icon": "question", "cells": cells})
        for q in questions:
            cells = list(pool.map(lambda h: _hotel_cell(h, q), hs))
            rows.append({"id": f"ask:{q.lower()}", "title": q[:1].upper() + q[1:], "icon": "question", "cells": cells})

    if price:
        cells = [{"state": MATCH, "value": f"{int(h['mock']['price_rub']):,} ₽".replace(",", " "), "sub": "за ночь",
                  "key": h["mock"]["price_rub"], "source": "mock",
                  "how": "Цена из карточки отеля (в прототипе — пример, как на сайте)."} for h in hs]
        _winners(cells)
        rows.append({"id": "price", "title": "Цена за ночь", "icon": "card", "cells": cells})

    for r in rows:
        r["custom"] = True
    return {"rows": rows, "by": by, "month": d.get("month"), "nothing": not rows}
