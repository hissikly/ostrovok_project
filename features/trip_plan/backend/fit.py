"""Насколько день по интересам получится у каждого отеля — для строки в списке и сортировки.

По готовым фактам, без прокладки маршрутов: ближайшее место каждого интереса (near:<spec> из
features/nearby), путь до пляжа (beach_route, иначе beach_distance), тишина ночью (noise).
Интерес «пешком», если ближайшее место в LIMIT минутах; «далеко» — с минутами; нет данных — «не знаем».
"""
from features.facts.backend import facts_for
from features.hotels.backend import hotels
from features.trip_plan.backend.interests import BY_ID
from features.trip_plan.backend.plan import LIMIT

SHORT = {"sea": "море", "culture": "музеи", "party": "бары", "walk": "парк", "food": "рестораны",
         "sport": "спорт", "kids": "площадки", "quiet": "тишина"}


def _minutes(facts, iid):
    """Минут пешком до ближайшего места интереса; None — не знаем; -1 — точно не нашли рядом."""
    if iid == "sea":
        r = next((f for f in facts if f["characteristic"] == "beach_route"), None)
        if r:
            return r["value"]["minutes"]
        b = next((f for f in facts if f["characteristic"] == "beach_distance"), None)
        return b["value"]["walk_min"] if b else None
    best, searched = None, False
    for spec in BY_ID[iid]["specs"]:
        f = next((x for x in facts if x["characteristic"] == f"near:{spec}"), None)
        if not f:
            continue
        searched = True
        m = f["value"].get("walk_min")
        if m is not None and (best is None or m < best):
            best = m
    return best if best is not None else (-1 if searched else None)


def _quiet(facts):
    levels = [f["value"]["level"] for f in facts if f["characteristic"] == "noise"]
    if not levels:
        return None
    return any(lv in ("quiet", "calm") for lv in levels)


def hotel_fit(hotel_id, interests):
    facts = facts_for(hotel_id)
    good, far, unknown = [], [], []
    for iid in interests:
        if iid == "quiet":
            q = _quiet(facts)
            (unknown if q is None else good if q else far).append({"id": iid, "title": "шумно ночью"} if q is False else {"id": iid})
            continue
        m = _minutes(facts, iid)
        if m is None:
            unknown.append({"id": iid})
        elif 0 <= m <= LIMIT:
            good.append({"id": iid, "min": m})
        else:
            far.append({"id": iid, "min": m if m > 0 else None,
                        "title": f"{SHORT[iid]} — {m} мин" if m > 0 else f"{SHORT[iid]} — не рядом"})
    score = len(good) * 100 - sum(x.get("min", 0) for x in good) - len(unknown) * 30
    return {"good": len(good), "all": len(interests), "far": far, "unknown": len(unknown), "score": score}


def fit_all(interests):
    ids = [i for i in interests if i in BY_ID]
    return {h["id"]: hotel_fit(h["id"], ids) for h in hotels()} if ids else {}
