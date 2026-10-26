"""Пожелание к брони: собирается само из выбранного в «О!кне» и фактов, правилами, без LLM.

«Окна на запад, этаж 7 и выше, тихая сторона» — у каждого пункта причина и факты.
- сторона — та, что выбрал гость; причины: сколько моря из окна, закат над морем в месяц поездки, тише других;
- этаж — с какого этажа вид почти такой же, как с выбранного (доля моря ≥ 95% от выбранной):
  незачем просить 16-й, если с 7-го то же море;
- тихая сторона — если выбранная сторона среди самых тихих (не громче тишайшей на 3 дБ), а другая шумнее на 5+ дБ.
"""
from .context import context, hotel_facts

SIDE_TO = {"N": "на север", "E": "на восток", "S": "на юг", "W": "на запад"}
SIDE_ADJ = {"N": "северной", "E": "восточной", "S": "южной", "W": "западной"}
MONTH_IN = ["", "январе", "феврале", "марте", "апреле", "мае", "июне", "июле", "августе",
            "сентябре", "октябре", "ноябре", "декабре"]
SAME_VIEW = 0.95   # доля моря от выбранного этажа, при которой вид «почти такой же»


def brief(f: dict) -> dict:
    """Факт для показа гостю: источник, уверенность, дата и то, что нужно для «как узнали»."""
    return {k: f.get(k) for k in ("id", "characteristic", "scope", "value", "source", "confidence", "obtained_at", "evidence", "note", "level")
            if f.get(k) is not None}


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def _noise_name(v: dict) -> str:
    src = v.get("source") or {}
    return src.get("name") or src.get("kind_ru") or "улица"


def items(ctx: dict) -> list[dict]:
    fs, side, floor, month = ctx["facts"], ctx["side"], ctx["floor"], ctx["month"]
    if not side:
        return []
    out = []
    sea, sun, noise = fs.get("sea_view"), fs.get("sunset_view"), fs.get("noise")
    shares = {int(k): v for k, v in (sea["value"].get("share_by_floor") or {}).items()} if sea else {}
    share = shares.get(floor, 0)

    reasons, facts = [], []
    if share >= 0.6:
        reasons.append("море почти во всё окно")
    elif share >= 0.3:
        reasons.append("из окна видно море")
    elif share > 0.02:
        reasons.append("море видно краешком")
    if share > 0.02:
        facts.append(sea)
    if sun and month in sun["value"].get("months", []):
        reasons.append(f"закат над морем в {MONTH_IN[month]}")
        facts.append(sun)
    if reasons:
        out.append({"id": "side", "text": f"Окна {SIDE_TO[side]}", "reason": _cap(", ".join(reasons)),
                    "facts": [brief(f) for f in facts]})

    if share > 0.02 and len(shares) > 1:
        low = min(f for f, s in shares.items() if s >= SAME_VIEW * share)
        top = max(shares)
        if low > 1:
            if low < floor:
                why = f"С {low}-го этажа море почти как с {floor}-го"
            else:
                why = f"Ниже {floor}-го этажа моря заметно меньше" if floor < top else "С верхнего этажа моря больше всего"
            out.append({"id": "floor", "text": "Верхний этаж" if low == top else f"Этаж {low} и выше",
                        "reason": why, "min_floor": low, "facts": [brief(sea)]})

    if noise:
        sides = {}
        for f in hotel_facts(ctx["hotel_id"]):
            if f["characteristic"] == "noise" and f["scope"].startswith("facade:"):
                sides[f["scope"].split(":")[1]] = f
        if len(sides) > 1 and side in sides:
            mine = sides[side]["value"]["night_db"]
            quietest = min(f["value"]["night_db"] for f in sides.values())
            loud = max(sides.values(), key=lambda f: f["value"]["night_db"])
            if mine <= quietest + 3 and loud["value"]["night_db"] >= mine + 5 \
                    and sides[side]["value"]["level"] in ("quiet", "calm"):
                lv = loud["value"]
                out.append({"id": "quiet", "text": "Тихая сторона",
                            "reason": f"На {SIDE_ADJ[loud['scope'].split(':')[1]]} стороне ночью громче: рядом {_noise_name(lv)}",
                            "facts": [brief(sides[side]), brief(loud)]})
    return out


def text(its: list[dict]) -> str:
    return ", ".join(t if i == 0 else t[:1].lower() + t[1:] for i, t in enumerate(x["text"] for x in its))


def wish(hotel_id: str, month: int, facade: str | None, floor: int | None, drop: set[str] = frozenset()) -> dict | None:
    ctx = context(hotel_id, month, facade, floor)
    if ctx is None:
        return None
    its = [x for x in items(ctx) if x["id"] not in drop]
    floor_item = next((x for x in its if x["id"] == "floor"), None)
    return {"hotel_id": hotel_id, "facade": ctx["side"], "floor": ctx["floor"], "month": month,
            "min_floor": floor_item["min_floor"] if floor_item else None,
            "text": text(its), "items": its}
