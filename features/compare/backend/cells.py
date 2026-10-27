"""Клетка сравнения: короткое значение + пояснение из того же расчёта, что и линза поиска.

Линза говорит фразой («Море из окон на запад с 4-го этажа»), в таблице нужно коротко:
значение «С 4-го этажа» и пояснение «окна на запад». Для каждой клетки ещё и ключ сравнения —
число, по которому выбираем лучший отель в строке (меньше — лучше).
"""
from features.search.backend.lenses import LEVEL_RU, MATCH, NO, PARTIAL, SIDE, UNKNOWN, _dist, month_prep

MONTH_SHORT = ["", "янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
NEAR_SHORT = {"cafe": "Кафе", "grocery": "Продукты", "pharmacy_24": "Аптека 24 ч"}


def _side(f):
    return SIDE.get(f["scope"].split(":")[-1], "")


def _where(f):
    return f"окна на {_side(f)}" if f["scope"].startswith("facade:") else "у отеля"


def _quote(name):
    return name if any(c in name for c in "«\"„“") else f"«{name}»"


def _months(ms):
    ms = sorted(ms)
    return MONTH_SHORT[ms[0]] if len(ms) == 1 else f"{MONTH_SHORT[ms[0]]}–{MONTH_SHORT[ms[-1]]}"


def cell(lens_id: str, r: dict, facts: dict, ctx: dict) -> dict:
    """r — ответ линзы (state, text, facts), facts — факты отеля по id."""
    f = facts.get(r["facts"][0]) if r["facts"] else None
    out = {"state": r["state"], "value": r["text"], "sub": "", "key": None,
           "source": f["source"] if f else None, "confidence": r["confidence"],
           "obtained_at": f.get("obtained_at") if f else None}
    if r["state"] == UNKNOWN or not f:
        out.update(value="Не знаем", sub=r["text"][0].lower() + r["text"][1:])
        return out
    v = f["value"]
    if lens_id == "sea_view":
        if r["state"] == MATCH:
            n = v["from_floor"]
            out.update(value="С любого этажа" if n == 1 else f"С {n}-го этажа", sub=_where(f), key=n)
        elif r["state"] == PARTIAL:
            out.update(value="Краешком", sub=f"окна на {_side(f)}, с {v['glimpse_from']}-го этажа", key=100 + v["glimpse_from"])
        else:
            out.update(value="Не видно", sub="ни с одной стороны")
    elif lens_id == "sunset":
        if r["state"] == MATCH:
            out.update(value="Над морем", sub=_where(f), key=-len(v["months"]))
        elif f["characteristic"] == "sunset_view" and ctx.get("month"):
            months = sorted({m for x in r["facts"] if facts.get(x) for m in facts[x]["value"]["months"]})
            out.update(value=f"Не в {month_prep(ctx['month'])}", sub=f"бывает: {_months(months)}" if months else "")
        else:
            out.update(value="Не виден", sub="солнце садится не над морем")
    elif lens_id == "beach_near":
        if f["characteristic"] == "beach_route":
            out.update(value=f"{v['minutes']} мин", sub=f"{_dist(v['meters'])} пешком", key=v["minutes"])
        else:
            out.update(value=f"≈{v['walk_min']} мин", sub=f"{_dist(v['meters'])} по прямой", key=v["walk_min"])
    elif lens_id == "flat":
        if f["characteristic"] == "beach_route":
            up, back = v.get("climb_back_m", v["down_m"]), v["back_minutes"]
            if up <= 10:
                out.update(value=f"{back} мин", sub="почти ровно", key=up)
            else:
                out.update(value=f"{back} мин в гору", sub=f"подъём {up} м" + (", лестницы" if v.get("steps") else ""), key=up)
        else:
            out.update(value=f"{v['meters']} м над морем", sub="подъём от пляжа", key=v["meters"])
    elif lens_id == "quiet":
        src = v.get("source")
        sub = f"{src['kind_ru']} в {_dist(src['meters'])}" if src and v["level"] in ("noisy", "very_noisy") else _where(f)
        out.update(value=LEVEL_RU[v["level"]].capitalize(), sub=sub, key=v["night_db"])
    elif lens_id.startswith("near_"):
        if v["meters"] is None:
            out.update(value="Нет", sub=f"за {v['within_min']} мин пешком")
        else:
            out.update(value=f"{v['walk_min']} мин", sub=_quote(v["name"]) if v["name"] else v["kind"].lower(), key=v["walk_min"])
    return out


def near_items(facts_list: list[dict], specs: dict) -> list[dict]:
    """Строка «Рядом пешком»: кафе, продукты, круглосуточная аптека — минуты или «нет»."""
    by_char = {f["characteristic"]: f for f in facts_list if f["status"] == "active"}
    items = []
    for sid, title in NEAR_SHORT.items():
        f = by_char.get(f"near:{sid}")
        v = f["value"] if f else None
        items.append({"id": sid, "title": title, "icon": specs.get(sid, {}).get("icon", "pin"),
                      "minutes": v["walk_min"] if v and v["meters"] is not None else None,
                      "known": f is not None, "name": (v or {}).get("name") or "",
                      "within": (v or {}).get("within_min")})
    return items


# --- то, что знает отель (база знаний): завтрак, парковка, питомцы ---------------------------------------

def _yes(x):
    return x in ("да", "есть", True)


def answer_short(topic: str, value: dict, text: str) -> tuple[str, str, float | None]:
    """(значение, пояснение, ключ) по полям ответа; поля одинаковые у ответа отеля и у сайта."""
    v = value or {}
    if topic == "breakfast" and v.get("breakfast"):
        b = v["breakfast"]
        key = 0 if b == "включён" else 1 if b == "за доплату" else 2
        return b.capitalize(), v.get("kind") or "", key
    if topic == "parking" and v.get("parking"):
        if not _yes(v["parking"]):
            return "Нет", "", 1e6
        p = v.get("price_rub")
        sub = "бронировать заранее" if v.get("booking") == "нужно" else "заранее не нужно" if v.get("booking") else ""
        if p == 0:
            return "Бесплатно", sub, 0
        return (f"{p:,} ₽ в сутки".replace(",", " "), sub, p) if p else ("Есть", sub, 500)
    if topic == "pets" and ("dogs" in v or "cats" in v):
        dogs, cats = _yes(v.get("dogs")), _yes(v.get("cats"))
        val = "Собаки и кошки" if dogs and cats else "Собаки" if dogs else "Кошки" if cats else "Нельзя"
        if dogs and v.get("max_kg"):
            val = f"Собаки до {v['max_kg']} кг" + (" и кошки" if cats else "")
        sub = []
        if dogs and not cats:
            sub.append("кошки нельзя")
        if v.get("fee_rub"):
            sub.append(f"{v['fee_rub']:,} ₽ в сутки".replace(",", " "))
        elif v.get("fee_rub") == 0:
            sub.append("бесплатно")
        return val, ", ".join(sub), (0 if dogs and cats else 1 if dogs or cats else 3) + (v.get("fee_rub") or 0) / 1e5
    return text, "", None


DIFF_FIELDS = {"breakfast": ("breakfast",), "parking": ("parking", "price_rub"), "pets": ("dogs", "cats", "max_kg", "fee_rub")}


def disagree(topic: str, own: dict, site: dict) -> bool:
    """Отель и его сайт говорят разное по одному и тому же полю (поле есть у обоих)."""
    a, b = own or {}, site or {}
    return any(k in a and k in b and a[k] is not None and b[k] is not None and a[k] != b[k] for k in DIFF_FIELDS.get(topic, ()))
