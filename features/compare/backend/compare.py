"""Сравнение 2–4 отелей по собранным фактам.

Строки — те же линзы, что в поиске (включённые гостем — первыми, затем главные), плюс «Рядом пешком»
и под «Ещё» — то, что знает только отель (завтрак, парковка, питомцы). Значения берутся из тех же
функций, что и выдача, поэтому сравнение и поиск не могут разойтись.
Лучшее в строке выбираем по фактам: сначала «подходит», потом «частично», внутри — по числу
(этаж, минуты, подъём, шум). Если все отели в строке одинаковы — лучшего нет.
"""
from features.facts.backend import facts_for
from features.hotels.backend import hotel
from features.knowledge.backend import resolve
from features.nearby.backend import specs as nearby_specs
from features.search.backend.lenses import BY_ID, MATCH, NO, PARTIAL, UNKNOWN, month_prep
from features.search.backend.ranking import WEIGHT
from features.web_sources.backend import answer as web_answer

from .cells import answer_short, cell, disagree, near_items

DEFAULT = ["sea_view", "quiet", "beach_near", "flat", "sunset"]   # главное, если гость ничего не включил
CORE = ["sea_view", "quiet", "beach_near"]                       # по ним «лучше всех», когда запроса нет
EXTRA = ["breakfast", "parking", "pets"]                         # под «Ещё»: знает только отель
RANK = {MATCH: 0, PARTIAL: 1, NO: 2, UNKNOWN: 3}
MINUS_ORDER = ["flat", "beach_near", "sea_view", "quiet", "sunset"]
TITLE = {"beach_near": "До пляжа", "flat": "Обратно с пляжа"}   # в таблице — что измеряем, а не имя фильтра


def _winners(cells: list[dict]) -> None:
    """Помечает win у лучших клеток строки (могут делить первое место); все равны — никого."""
    scored = [(RANK[c["state"]], c["key"] if c["key"] is not None else 1e9) for c in cells]
    ok = [s for s, c in zip(scored, cells) if c["state"] in (MATCH, PARTIAL) and not c.get("split")]
    if not ok or len(set(scored)) == 1:
        return
    best = min(ok)
    for s, c in zip(scored, cells):
        c["win"] = s == best and c["state"] in (MATCH, PARTIAL) and not c.get("split")


def _score(results: list[dict]) -> float:
    if not results:
        return 0
    return sum(WEIGHT[r["state"]] * (0.5 + 0.5 * (r["confidence"] or 0)) for r in results) / len(results)


def _ddmm(d):
    return f"{d[8:10]}.{d[5:7]}" if d else ""


def _answer_cell(hid: str, topic: str, ctx: dict) -> dict:
    a = resolve(hid, topic, ctx)
    if a["status"] != "answered":
        return {"state": UNKNOWN, "value": "Не знаем", "sub": "", "key": None, "ask": topic if a["can_ask_hotel"] else None,
                "how": "Ни отель, ни его сайт этого не сообщали. Вопрос уйдёт отелю, обычно отвечают за 1–3 дня."}
    val, sub, key = answer_short(topic, a.get("value"), a["text"])
    out = {"state": MATCH if key is not None else PARTIAL, "value": val, "sub": sub, "key": key,
           "source": a.get("source"), "confidence": a.get("confidence"), "level": a["level"],
           "how": f"{a['note']}, {_ddmm(a.get('obtained_at'))}." if a.get("obtained_at") else f"{a['note']}."}
    site = web_answer(hid, topic) if a["level"] == "hotel" else None
    if site and disagree(topic, a.get("value"), site.get("value")):
        s_val, s_sub, _ = answer_short(topic, site["value"], site["text"])
        out["split"] = {"hotel": val.lower(), "site": s_val.lower(), "quote": site.get("quote"), "url": site.get("url")}
        out["how"] = f"{a['note']}, {_ddmm(a.get('obtained_at'))}. На сайте отеля: «{site.get('quote') or site['text']}». Уточняем у отеля, пока советуем проверить при бронировании."
    return out


def compare(ids: list[str], lens_ids: list[str], ctx: dict) -> dict:
    hs = [hotel(i) for i in ids]
    query = [i for i in dict.fromkeys(lens_ids) if i in BY_ID]
    shown = query + [i for i in DEFAULT if i not in query]
    facts = {h["id"]: facts_for(h["id"]) for h in hs}
    by_id = {h["id"]: {f["id"]: f for f in facts[h["id"]]} for h in hs}

    lens_res = {l: [BY_ID[l]["fn"](facts[h["id"]], ctx) for h in hs] for l in shown}
    rows = []
    for l in shown:
        cells = [cell(l, r, by_id[h["id"]], ctx) for r, h in zip(lens_res[l], hs)]
        _winners(cells)
        title = f"Закат в {month_prep(ctx['month'])}" if l == "sunset" and ctx.get("month") else TITLE.get(l, BY_ID[l]["title"])
        rows.append({"id": l, "title": title, "icon": BY_ID[l]["icon"], "query": l in query, "cells": cells})
    specs = {s["id"]: s for s in nearby_specs()}
    rows.append({"id": "near", "title": "Рядом пешком", "icon": "walk", "query": False, "kind": "near",
                 "cells": [{"items": near_items(facts[h["id"]], specs), "source": "computed:osm-poi+walk"} for h in hs]})
    for t in EXTRA:
        cells = [_answer_cell(h["id"], t, ctx) for h in hs]
        _winners(cells)
        rows.append({"id": t, "title": {"breakfast": "Завтрак", "parking": "Парковка", "pets": "С питомцем"}[t],
                     "icon": {"breakfast": "fork", "parking": "parking", "pets": "paw"}[t], "query": False, "extra": True,
                     "cells": cells})

    # «сколько условий запроса выполнено» и «лучше всех» — по запросу, а без него — по главному
    basis = query or CORE
    base_res = {l: lens_res.get(l) or [BY_ID[l]["fn"](facts[h["id"]], ctx) for h in hs] for l in basis}
    scores = [_score([base_res[l][j] for l in basis]) for j in range(len(hs))]
    order = sorted(range(len(hs)), key=lambda j: -scores[j])
    best = order[0] if len(hs) > 1 and scores[order[0]] > scores[order[1]] else None

    out_hotels = []
    for j, h in enumerate(hs):
        met = sum(base_res[l][j]["state"] == MATCH for l in basis)
        out_hotels.append({"id": h["id"], "name": h["name"], "stars": h["stars"], "stars_mock": h.get("stars_mock", False),
                           "rating": h["mock"]["rating"], "reviews": h["mock"]["reviews"], "price_rub": h["mock"]["price_rub"],
                           "met": met, "of": len(basis), "minus": _minus(j, shown, lens_res), "best": j == best})
    return {"lenses": query, "basis": "query" if query else "core", "month": ctx.get("month"),
            "hotels": out_hotels, "rows": rows}


def _minus(j: int, shown: list[str], lens_res: dict) -> str | None:
    """Главный минус отеля одной фразой: сначала «нет», потом «частично», потом «не знаем»."""
    order = [l for l in MINUS_ORDER if l in shown] + [l for l in shown if l not in MINUS_ORDER]
    for state in (NO, PARTIAL):
        for l in order:
            r = lens_res[l][j]
            if r["state"] == state:
                return r["text"]
    unknown = [BY_ID[l]["title"].lower() for l in order if lens_res[l][j]["state"] == UNKNOWN]
    return f"Пока не знаем: {', '.join(unknown)}" if unknown else None
