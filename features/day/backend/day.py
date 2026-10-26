"""«Твой день здесь»: лента одного дня поездки, собранная только из готовых фактов.

Сцена появляется, только если для неё есть факт; время — из фактов (восход в окне, закат)
или из шаблона дня (кофе 08:30, пляж 10:00, обратно 13:00, ужин 20:00, ночь 23:00).
Сцена: {time, icon, title, note, good, fact_ids, facts}. good=False — честный подвох.
facts — сами факты сцены (источник, уверенность, дата), чтобы фронт показал «как узнали».
"""
import datetime as dt

from core.seed import load
from features.facts.backend import facts_for
from features.hotels.backend import hotel

SIDES = "NESW"
SIDE_TO = {"N": "на север", "E": "на восток", "S": "на юг", "W": "на запад"}
MONTH_IN = ["", "январе", "феврале", "марте", "апреле", "мае", "июне", "июле", "августе",
            "сентябре", "октябре", "ноябре", "декабре"]
NEAR_OK = 10          # минут пешком — «рядом», ради этого стоит сцена
WAKE_BEFORE = "08:00"  # солнце в окне раньше — разбудит
FLOOR_M = 3           # метров на этаж — чтобы подъём было с чем сравнить
KIDS_CLIMB = 15       # подъём в метрах, с которого коляску толкать тяжело


def _plural(n, one, few, many):
    n = abs(n) % 100
    if 11 <= n <= 14:
        return many
    return {1: one, 2: few, 3: few, 4: few}.get(n % 10, many)


def _min(n):
    return f"{n} {_plural(n, 'минута', 'минуты', 'минут')}"


def _min_in(n):
    """«в 4 минутах», «в 1 минуте»."""
    return f"в {n} {_plural(n, 'минуте', 'минутах', 'минутах')}"


def _quote(name):
    return "" if not name else name if any(q in name for q in "«\"„“") else f"«{name}»"


def _scope_side(f):
    return f["scope"].split(":")[1] if f["scope"].startswith("facade:") else None


def _pick_side(facts, char, side):
    """Факт этой стороны, иначе — у отеля целиком."""
    by = [f for f in facts if f["characteristic"] == char]
    return (next((f for f in by if _scope_side(f) == side), None)
            or next((f for f in by if f["scope"] == "hotel"), None))


def _scene(time, icon, title, note, good, facts):
    return {"time": time, "icon": icon, "title": title, "note": note, "good": good,
            "fact_ids": [f["id"] for f in facts], "facts": facts}


# ---------- сцены ----------

def _window(hotel_id, side, floor):
    """Окно для сцен утра и вечера: (данные «О!кна» стороны, этаж) или (None, None)."""
    d = load(f"okno/{hotel_id}.json")
    if not d or not d["facades"]:
        return None, None, None
    if side not in d["facades"]:
        side = "W" if "W" in d["facades"] else next(iter(d["facades"]))
    f = d["facades"][side]
    floors = sorted(int(k) for k in f["floors"])
    fl = min(floors, key=lambda x: abs(x - (floor or floors[-1])))
    return d, side, fl


def morning(hotel_id, d, side, floor, month):
    m = (load("day_morning.json") or {}).get("hotels", {}).get(hotel_id)
    if not m or side not in m or not m[side]:
        return None
    floors = sorted(int(k) for k in m[side])
    fl = min(floors, key=lambda x: abs(x - floor))
    sun_in, rise = m[side][str(fl)][month - 1], m["sunrise"][month - 1]
    fact = {
        "id": f"{hotel_id}:morning_sun:facade:{side}", "hotel_id": hotel_id, "scope": f"facade:{side}",
        "characteristic": "morning_sun", "value": {"month": month, "floor": fl, "sunrise": rise, "sun_in_window": sun_in},
        "confidence": d["confidence"], "source": "computed:horizon+sun", "method_version": "morning-sun@0.1",
        "evidence": {"method": "профиль горизонта «О!кна» и положение солнца 15-го числа", "profile_floor": fl},
        "obtained_at": (load("day_morning.json") or {}).get("obtained_at"), "valid_until": None, "status": "active",
    }
    if sun_in and sun_in < WAKE_BEFORE:
        return _scene(sun_in, "sunset", f"Солнце заглянет в окно в {sun_in}",
                      f"Рассвет в {rise}. Если любите поспать, пригодятся плотные шторы", False, [fact])
    if sun_in:
        return _scene("07:00", "sunset", "Солнце не разбудит",
                      f"В окно оно заглянет только к {sun_in}", True, [fact])
    return _scene("07:00", "sunset", "Солнце не разбудит",
                  f"Окна {SIDE_TO[side]}: утром солнце с другой стороны здания", True, [fact])


def near_scene(facts, spec, time, icon, title):
    f = next((x for x in facts if x["characteristic"] == f"near:{spec}"), None)
    if not f or f["value"].get("meters") is None or f["value"]["walk_min"] > NEAR_OK:
        return None
    v = f["value"]
    where = f"{_min_in(v['walk_min'])} пешком"
    return _scene(time, icon, title, f"{_quote(v['name'])}, {where}" if v.get("name") else where.capitalize(), True, [f])


def _climate(h, month):
    """Погода и вода в месяц поездки — из фичи climate, когда она есть (бриф 4)."""
    try:
        from features.climate.backend import climate
    except ImportError:
        return None
    try:
        return climate(h["lat"], h["lon"], month)
    except Exception:  # noqa: BLE001 — чужая фича не должна ронять ленту
        return None


def beach(facts, h, month, kids):
    """Сцены пляжа: туда (10:00) и обратно (13:00)."""
    route = next((f for f in facts if f["characteristic"] == "beach_route"), None)
    straight = next((f for f in facts if f["characteristic"] == "beach_distance"), None)
    # отель у самой воды, а маршрут по графу вышел длинным — граф не дошёл до пляжа рядом;
    # верим замеру по карте (inbox 26.10: «Чайка»)
    if route and straight and straight["value"]["meters"] <= 150 and route["value"]["minutes"] > straight["value"]["walk_min"] + 10:
        route = None
    cl = _climate(h, month)
    water = cl and cl.get("water")
    water_note = f"Вода в {MONTH_IN[month]} около {round(water)}°" if water else ""
    out = []
    if route:
        v = route["value"]
        down = f"вниз {v['down_m']} м" if v["down_m"] >= 10 else "почти ровно"
        notes = [down] + [s for s in (v["steps"] and "лестницы", v["underpass"] and "подземный переход",
                                      v["rail"] and "переход через железную дорогу") if s]
        out.append(_scene("10:00", "beach", f"На пляж {_min(v['minutes'])} пешком",
                          ". ".join(x for x in ((", ".join(notes)).capitalize(), water_note) if x),
                          v["minutes"] <= 15, [route]))
        climb = v.get("climb_back_m", v["up_m"])
        stairs = v["steps"] or v["underpass"] or v["bridge"]
        if kids and (climb >= KIDS_CLIMB or stairs):
            why = f"подъём {climb} м" if climb >= KIDS_CLIMB else ""
            why = ", ".join(x for x in (why, stairs and "есть лестницы") if x)
            out.append(_scene("13:00", "child", f"Обратно {_min(v['back_minutes'])}, с коляской тяжело",
                              why.capitalize(), False, [route]))
        elif climb >= 25:
            out.append(_scene("13:00", "mountain", f"Обратно {_min(v['back_minutes'])} в гору",
                              f"Подъём {climb} м, как на {round(climb / FLOOR_M)}-й этаж пешком", False, [route]))
        elif climb >= 10:
            out.append(_scene("13:00", "mountain", f"Обратно {_min(v['back_minutes'])}",
                              f"Небольшой подъём, {climb} м", v["back_minutes"] <= 15, [route]))
        else:
            out.append(_scene("13:00", "check", f"Обратно {_min(v['back_minutes'])}, почти ровно",
                              "Можно сбегать в номер в обед", True, [route]))
    elif straight:
        v = straight["value"]
        dist = f"{v['meters']} м" if v["meters"] < 1000 else f"{v['meters'] / 1000:.1f} км".replace(".", ",")
        title = "Море прямо у отеля" if v["meters"] <= 150 else f"До пляжа {dist}"
        out.append(_scene("10:00", "beach", title,
                          ". ".join(x for x in (f"{_min(v['walk_min'])} пешком".capitalize(), water_note) if x),
                          v["walk_min"] <= 15, [straight]))
    return out


def evening(hotel_id, d, side, floor, month, facts):
    v = d["facades"][side]["floors"][str(floor)]
    s = next((x for x in v["sun"] if x["month"] == month), None)
    if s is None:
        return None
    fact = next((f for f in facts if f["characteristic"] == "sunset_view" and _scope_side(f) == side), None) \
        or next((f for f in facts if f["characteristic"] == "sea_view" and _scope_side(f) == side), None)
    fs = [fact] if fact else []
    if s["sets_into_sea"]:
        return _scene(s["sunset_astro"], "sunset", "Закат над морем прямо из окна",
                      f"Солнце сядет в море в {s['sunset_astro']}", True, fs)
    if s["sun_hidden_at"] and s["minutes_earlier"] <= 3:
        return _scene(s["sunset_astro"], "sunset", "Закат виден из окна",
                      "Солнце сядет за дальними домами у горизонта", True, fs)
    if s["sun_hidden_at"] and s["hidden_by"] in ("building", "terrain"):
        what = "соседний дом" if s["hidden_by"] == "building" else "склон"
        return _scene(s["sun_hidden_at"], "sunset", f"В {s['sun_hidden_at']} закат закроет {what}",
                      f"За {_min(s['minutes_earlier'])} до заката в {s['sunset_astro']}", False, fs)
    vp = next((f for f in facts if f["characteristic"] == "near:viewpoint" and f["value"].get("meters") is not None
               and f["value"]["walk_min"] <= NEAR_OK), None)
    note = (f"Смотреть его лучше со смотровой {_quote(vp['value']['name'])}, {_min_in(vp['value']['walk_min'])}"
            if vp and vp["value"].get("name") else "Солнце садится с другой стороны здания")
    return _scene(s["sunset_astro"], "sunset", "Заката из окна не видно", note, False, fs + ([vp] if vp else []))


def night(facts, side):
    f = _pick_side(facts, "noise", side)
    if not f:
        return None
    v = f["value"]
    src = v.get("source") or {}
    if v["level"] == "quiet":
        return _scene("23:00", "moon", "Ночью тихо", f"Около {v['night_db']} дБ, как в тихой комнате", True, [f])
    if v["level"] == "calm":
        return _scene("23:00", "moon", "Ночью спокойно", "Улицу почти не слышно", True, [f])
    kind, name = src.get("kind"), src.get("name")
    what = {"runway": "Слышны самолёты", "rail": "Слышны поезда"}.get(kind) or (
        f"Рядом {src.get('kind_ru', 'бар')} {_quote(name)}" if kind in ("bar", "pub", "nightclub")
        else f"Рядом {name}" if name else f"Рядом {src.get('kind_ru', 'улица')}")
    note = f"{what.strip()}, ночью около {v['night_db']} дБ"
    quieter = [x for x in facts if x["characteristic"] == "noise" and _scope_side(x)
               and x["value"]["level"] in ("quiet", "calm")]
    if quieter and _scope_side(f):
        best = min(quieter, key=lambda x: x["value"]["night_db"])
        note += f". Окна {SIDE_TO[_scope_side(best)]} тише"
        return _scene("23:00", "volume", "Ночью шумно", note, False, [f, best])
    return _scene("23:00", "volume", "Ночью шумно", note + ". Возьмите беруши", False, [f])


def _airport(h):
    """Первая сцена — прилёт, когда готова фича airport (бриф 5)."""
    try:
        from features.airport.backend import arrival
    except ImportError:
        return None
    try:
        return arrival(h)
    except Exception:  # noqa: BLE001
        return None


def day(hotel_id: str, month: int, facade: str | None = None, floor: int | None = None, mode: str | None = None):
    h = hotel(hotel_id)
    if h is None:
        return None
    facts = facts_for(hotel_id)
    kids = mode == "kids"
    d, side, fl = _window(hotel_id, facade, floor)
    side = side or facade
    scenes = [_airport(h)]
    if d:
        scenes.append(morning(hotel_id, d, side, fl, month))
    scenes.append(near_scene(facts, "cafe", "08:30", "cup", "Кофе рядом"))
    scenes += beach(facts, h, month, kids)
    if kids:
        scenes.append(near_scene(facts, "playground", "17:00", "child", "Детская площадка рядом"))
    if d:
        scenes.append(evening(hotel_id, d, side, fl, month, facts))
    scenes.append(near_scene(facts, "restaurant", "20:00", "fork", "Ужин рядом"))
    scenes.append(night(facts, side))
    scenes.append(near_scene(facts, "pharmacy_24", "23:30", "cross", "Круглосуточная аптека рядом")
                  or near_scene(facts, "grocery_24", "23:30", "cart", "Магазин рядом работает ночью"))
    scenes = sorted((s for s in scenes if s), key=lambda s: s["time"])
    return {"hotel_id": hotel_id, "month": month, "facade": side if d else None, "floor": fl,
            "mode": "kids" if kids else None, "scenes": scenes, "built_at": dt.date.today().isoformat()}
