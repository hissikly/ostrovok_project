"""Подбор: каждая включённая линза оценивает отель по его фактам, отели сортируются по совпадению.

Вклад линзы: подходит 1, частично 0,5, нет и «не знаем» 0 — и умножается на доверие к факту
(0,5 + 0,5·уверенность), чтобы шаткий расчёт не обгонял надёжный.
Отели, про которые мы чего-то не знаем, не выкидываем — показываем ниже и честно пишем «не знаем».
"""
from features.facts.backend import all_facts
from features.hotels.backend import hotels

from .lenses import BY_ID, MATCH, NO, PARTIAL, UNKNOWN

WEIGHT = {MATCH: 1.0, PARTIAL: 0.5, NO: 0.0, UNKNOWN: 0.0}


def search(lens_ids: list[str], ctx: dict) -> dict:
    lenses = [BY_ID[i] for i in lens_ids if i in BY_ID]
    facts = all_facts()
    summary = {l["id"]: {MATCH: 0, PARTIAL: 0, NO: 0, UNKNOWN: 0} for l in lenses}
    rows = []
    for h in hotels():
        reasons = []
        for l in lenses:
            r = l["fn"](facts.get(h["id"], []), ctx)
            summary[l["id"]][r["state"]] += 1
            reasons.append({"lens": l["id"], **r})
        score = sum(WEIGHT[r["state"]] * (0.5 + 0.5 * (r["confidence"] or 0)) for r in reasons)
        score = score / len(lenses) if lenses else 0
        states = [r["state"] for r in reasons]
        rows.append({"id": h["id"], "score": round(score, 3), "fit": fit(states),
                     "unknown": states.count(UNKNOWN), "price_rub": h["mock"]["price_rub"],
                     "reasons": reasons})
    rows.sort(key=lambda r: (-r["score"], r["unknown"], r["price_rub"]))
    return {"lenses": [l["id"] for l in lenses], "summary": summary,
            "counts": {k: sum(r["fit"] == k for r in rows) for k in ("all", "some", "unknown", "none")},
            "hotels": rows}


def fit(states: list[str]) -> str:
    """all — подходит по всем линзам; some — хоть по одной; unknown — не знаем, но и «нет» не было; none — не подходит."""
    if not states:
        return "all"
    if all(s == MATCH for s in states):
        return "all"
    if any(s in (MATCH, PARTIAL) for s in states):
        return "some"
    if all(s == UNKNOWN for s in states):
        return "unknown"
    return "none"
