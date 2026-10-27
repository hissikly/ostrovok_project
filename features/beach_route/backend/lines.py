"""Линия от моря — как её понимают в Сочи: 1-я, 2-я, 3-я, дальше.

Считаем по пешему пути до пляжа (`beach_route`), без него — по прямой (`beach_distance` ×1,3):
1-я ≤ 250 м, 2-я ≤ 500 м, 3-я ≤ 1 км, дальше — 4. Если по пути большая дорога (50+ м вдоль неё)
или ж/д переезд — это уже не 1-я линия, а 2-я. Новых данных нет — только уже посчитанные факты.
"""


def sea_line(facts: list[dict]) -> int | None:
    by = {f["characteristic"]: f["value"] for f in facts if f["characteristic"] in ("beach_route", "beach_distance")}
    route, straight = by.get("beach_route"), by.get("beach_distance")
    if route:
        meters = route["meters"]
    elif straight:
        meters = straight["meters"] * 1.3
    else:
        return None
    line = 1 if meters <= 250 else 2 if meters <= 500 else 3 if meters <= 1000 else 4
    if line == 1 and route and (route["major_m"] >= 50 or route["rail"] > 0):
        line = 2
    return line
