"""Факты одной поездки: отель, выбранные в «О!кне» сторона и этаж, месяц, с ребёнком или нет.

Всё, из чего «Моя поездка» собирает пожелание, обещание и чемодан, — готовые факты:
- факты отеля (features.facts), у фактов по сторонам здания — факт выбранной стороны;
- факты сцен «Ваш день» (features.day): утреннее солнце в окне, утренний кофе, честный путь к морю
  (у отеля прямо у воды лента верит замеру по карте, а не длинному маршруту — так же делаем и мы);
- общее знание из базы знаний (features.knowledge): вода в море по месяцам, какие пляжи, кроватка — ключ «kb:<тема>».
Ничего не придумываем: нет факта — нет ключа.
"""
from features.day.backend import day
from features.facts.backend import facts_for
from features.hotels.backend import hotel
from features.knowledge.backend import resolve

ALL_STOPS = {"coffee", "beach", "kids", "sunset", "dinner", "night"}   # лента-справка, без выходов из отеля
KB_TOPICS = ("swim", "beach_type", "crib", "breakfast")
FEEDBACK = "guest_feedback"


def _side(f):
    return f["scope"].split(":")[1] if f["scope"].startswith("facade:") else None


def hotel_facts(hotel_id: str) -> list[dict]:
    """Факты отеля без наших же наблюдений гостей."""
    return [f for f in facts_for(hotel_id) if f["characteristic"] != FEEDBACK]


def context(hotel_id: str, month: int, facade: str | None, floor: int | None, kids: bool = False) -> dict | None:
    h = hotel(hotel_id)
    if h is None:
        return None
    facts = hotel_facts(hotel_id)
    d = day(hotel_id, month, facade, floor, "kids" if kids else None, ALL_STOPS)
    side = d["facade"] or facade
    by = {}
    for f in facts:
        s = _side(f)
        if s and s != side:
            continue
        if s or f["characteristic"] not in by:   # факт стороны важнее факта «у отеля целиком»
            by[f["characteristic"]] = f
    for s in d["scenes"]:
        for f in s["facts"]:
            if f["characteristic"] not in by and (_side(f) in (None, side)):
                by[f["characteristic"]] = f
    beach_scene = next((s for s in d["scenes"] if s["icon"] == "beach"), None)
    if beach_scene and not any(f["characteristic"] == "beach_route" for f in beach_scene["facts"]):
        by.pop("beach_route", None)
    for t in KB_TOPICS:
        r = resolve(hotel_id, t, {"month": month})
        if r.get("status") == "answered" and r.get("value") is not None:
            by[f"kb:{t}"] = {"id": f"{hotel_id}:kb:{t}", "hotel_id": hotel_id, "characteristic": f"kb:{t}",
                             "scope": "hotel", "value": r["value"], "text": r["text"], "note": r.get("note"),
                             "level": r.get("level"), "source": r.get("source"), "confidence": r.get("confidence"),
                             "obtained_at": r.get("obtained_at")}
    return {"hotel": h, "hotel_id": hotel_id, "month": month, "side": side, "floor": d["floor"] or floor,
            "kids": kids, "facts": by, "day": d}
