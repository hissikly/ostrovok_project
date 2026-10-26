"""«Что мы вам обещали»: 3–5 фактов, на которых держался выбор, — сохраняются вместе с бронью.

Берём то, что гость видел в карточке, для его стороны и этажа: море из окна, закат, путь к пляжу
и обратно, тишина ночью, и одно — со слов отеля (бассейн, завтрак), если есть.
Формулировки — те же, что в ленте «Ваш день» (features.day), чтобы обещание звучало так же, как карточка.
"""
from .context import context
from .wish import brief

SIDE_TO = {"N": "на север", "E": "на восток", "S": "на юг", "W": "на запад"}
MAX = 5


def _scene(d, pred):
    return next((s for s in d["scenes"] if s.get("kind") != "walk" and pred(s)), None)


def _chars(s):
    return {f["characteristic"] for f in s["facts"]}


def items(ctx: dict) -> list[dict]:
    fs, side, floor, d = ctx["facts"], ctx["side"], ctx["floor"], ctx["day"]
    out = []
    sea = fs.get("sea_view")
    if sea and side:
        share = (sea["value"].get("share_by_floor") or {}).get(str(floor), 0)
        if share > 0.02:
            title = "Море из окна" if share >= 0.3 else "Море краешком из окна"
            out.append({"id": sea["id"], "icon": "waves", "title": title,
                        "note": f"Окна {SIDE_TO[side]}, {floor} этаж", "facts": [brief(sea)]})
    sunset = _scene(d, lambda s: s["icon"] == "sunset" and s["title"].startswith("Закат") and s["good"])
    if sunset and sunset["facts"]:
        out.append({"id": sunset["facts"][0]["id"], "icon": "sunset", "title": sunset["title"],
                    "note": f"В {sunset['time']}. {sunset['note']}", "facts": [brief(f) for f in sunset["facts"]]})
    beach = _scene(d, lambda s: s["icon"] == "beach")
    if beach and beach["facts"]:
        back = _scene(d, lambda s: s.get("time") == "13:00" and "beach_route" in _chars(s))
        note = f"{back['title']}. {back['note']}" if back else beach["note"]
        out.append({"id": beach["facts"][0]["id"], "icon": "beach", "title": beach["title"], "note": note,
                    "facts": [brief(beach["facts"][0])]})
    night = _scene(d, lambda s: s["time"] == "23:00" and "noise" in _chars(s))
    if night:
        out.append({"id": night["facts"][0]["id"], "icon": night["icon"], "title": night["title"], "note": night["note"],
                    "facts": [brief(night["facts"][0])]})
    site = _scene(d, lambda s: any(c.startswith("web:") for c in _chars(s)))
    if site and len(out) < MAX:
        f = site["facts"][0]
        out.append({"id": f["id"], "icon": site["icon"], "title": f["value"].get("text") or site["title"],
                    "note": "Так пишет сайт отеля", "facts": [brief(f)]})
    return out[:MAX]


def promise(hotel_id: str, month: int, facade: str | None, floor: int | None) -> list[dict] | None:
    ctx = context(hotel_id, month, facade, floor)
    return None if ctx is None else items(ctx)
