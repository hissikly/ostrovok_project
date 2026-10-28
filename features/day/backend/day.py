"""«Твой день здесь»: лента одного дня поездки, собранная только из готовых фактов.

Сцена появляется, только если для неё есть факт; время — из фактов (восход в окне, закат)
или из шаблона дня (завтрак 08:30, пляж 10:00, обратно 13:00, ужин 20:30, ночь 23:00).
Сцена: {time, icon, title, note, good, fact_ids, facts, stop?}. good=False — честный подвох.
facts — сами факты сцены (источник, уверенность, дата), чтобы фронт показал «как узнали».
stop — место вне отеля {id, name, lat, lon, at, stay, to}: куда гость выходит из отеля.

Выходы из отеля (_outings): остановки по времени; между близкими по времени идём сразу, иначе
сначала возвращаемся в отель. В ленту добавляются строки пути (kind="walk": когда вышли, сколько
идти, подъём), у посещённых мест — время прихода и «до скольких» (visit). Убранные гостем места
(skip) остаются в ленте справкой, без пути.
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


def _scene(time, icon, title, note, good, facts, stop=None):
    s = {"time": time, "icon": icon, "title": title, "note": note, "good": good,
         "fact_ids": [f["id"] for f in facts], "facts": facts}
    if stop:
        s["stop"] = stop
    return s


def _stop(sid, v, at, stay, to, here):
    """Место вне отеля: координаты, когда там быть (at), сколько минут там (stay),
    куда идём («до кофейни») и как сцена звучит, когда гость там (here: title, note)."""
    if v.get("lat") is None or v.get("lon") is None:
        return None
    return {"id": sid, "name": v.get("name") or v.get("kind") or "", "lat": v["lat"], "lon": v["lon"],
            "at": at, "stay": stay, "to": to, "here": here}


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
        return _scene(sun_in, "sunset", "Солнце заглянет в окно рано",
                      f"Рассвет в {rise}. Любите поспать — задёрните плотные шторы с вечера", False, [fact])
    if sun_in:
        return _scene("07:00", "sunset", "Солнце не разбудит",
                      f"В окно оно заглянет только к {sun_in}, можно выспаться", True, [fact])
    note = "Утром солнце с другой стороны здания" if side == "W" else "Прямого солнца в окне утром не будет"
    return _scene("07:00", "sunset", "Солнце не разбудит", note, True, [fact])


def _near(facts, spec, limit=NEAR_OK):
    f = next((x for x in facts if x["characteristic"] == f"near:{spec}"), None)
    return f if f and f["value"].get("meters") is not None and f["value"]["walk_min"] <= limit else None


def _none_near(facts, spec):
    """Факт «в N минутах пешком такого нет» (поиск был, ничего не нашли)."""
    f = next((x for x in facts if x["characteristic"] == f"near:{spec}"), None)
    return f if f and f["value"].get("meters") is None and f["value"].get("within_min", 0) >= NEAR_OK else None


# куда идём и что там: id остановки → (минут на месте, «до …», заголовок на месте)
VISIT = {
    "kids": (90, {"playground": "до площадки", "waterpark": "до аквапарка"}, {"playground": "На детской площадке", "waterpark": "В аквапарке"}),
    "dinner": (90, {"restaurant": "до ресторана", "cafe": "до кафе"}, {"restaurant": "Ужин", "cafe": "Ужин"}),
    "night": (10, {"pharmacy_24": "до аптеки", "grocery_24": "до магазина"}, {"pharmacy_24": "Аптека работает ночью", "grocery_24": "Магазин работает ночью"}),
}


def near_scene(facts, spec, time, icon, title, limit=NEAR_OK, stop=None):
    f = _near(facts, spec, limit)
    if not f:
        return None
    v = f["value"]
    where = f"{_min_in(v['walk_min'])} пешком"
    st = None
    if stop:
        stay, to, here = VISIT[stop]
        st = _stop(stop, v, time, stay, to[spec], {"title": here[spec], "note": _quote(v.get("name"))})
    return _scene(time, icon, title, f"{_quote(v['name'])}, {where}" if v.get("name") else where.capitalize(), True, [f], st)


def _site(facts, topic):
    """Факт с сайта отеля (web_sources): там дословная цитата и ссылка."""
    return next((f for f in facts if f["characteristic"] == f"web:{topic}"), None)


def _coffee_fact(hotel_id):
    """Утреннее кафе из pipeline/morning_cafes.py: по часам и кухне OSM, а не любое amenity=cafe."""
    seed = load("day_cafes.json") or {}
    c = (seed.get("hotels") or {}).get(hotel_id)
    if not c or c["walk_min"] > NEAR_OK:
        return None
    return {"id": f"{hotel_id}:morning_coffee", "hotel_id": hotel_id, "scope": "hotel", "characteristic": "morning_coffee",
            "value": {k: c[k] for k in ("name", "lat", "lon", "walk_min", "meters", "opens", "why")},
            "confidence": c["confidence"], "source": "computed:osm-poi+walk", "method_version": "morning-cafe@0.1",
            "evidence": {"osm": c["osm"], "why": c["why"]}, "obtained_at": seed.get("obtained_at"),
            "valid_until": None, "status": "active"}


def breakfast(hotel_id, facts):
    f = _site(facts, "breakfast")
    if f and f["value"].get("breakfast") in ("есть", "включён", "за доплату"):
        b, kind = f["value"]["breakfast"], f["value"].get("kind")
        price = {"включён": "уже в цене", "за доплату": "за доплату"}.get(b)
        bits = [x for x in (price, kind) if x]
        note = (", ".join(bits).capitalize() + ", по словам отеля") if bits else "По словам отеля"
        return _scene("08:30", "cup", "Завтрак в отеле", note, True, [f])
    f = _coffee_fact(hotel_id)
    if not f:
        return None
    v = f["value"]
    what = f"открыто с {v['opens']}" if v.get("opens") else v["why"]
    here = {"title": f"Кофе в {_quote(v['name'])}", "note": what.capitalize()}
    return _scene("08:30", "cup", "Кофе утром", f"{_quote(v['name'])}, {what}, {_min_in(v['walk_min'])} пешком", True, [f],
                  _stop("coffee", v, "08:30", 30, "до кофейни", here))


def pool(facts):
    f = _site(facts, "pool")
    if not f or f["value"].get("pool") != "есть":
        return None
    v = f["value"]
    bits = [x for x in (v.get("kind"), v.get("heated") and "с подогревом") if x]
    note = (", ".join(bits).capitalize() + ". " if bits else "") + "По словам отеля"
    return _scene("15:00", "waves", "После обеда — бассейн", note, True, [f])


def dinner(facts):
    s = near_scene(facts, "restaurant", "20:30", "fork", "Ужин рядом", stop="dinner") \
        or near_scene(facts, "cafe", "20:30", "fork", "Поужинать есть где", stop="dinner")
    if s:
        return s
    gone = [f for f in (_none_near(facts, "restaurant"), _none_near(facts, "cafe")) if f]
    if len(gone) == 2:
        return _scene("20:30", "fork", "Ужинать придётся не за углом",
                      "В 10 минутах пешком нет ни кафе, ни ресторана", False, gone)
    return None


def kids_afternoon(facts):
    s = near_scene(facts, "playground", "17:00", "child", "Детская площадка рядом", stop="kids")
    if s:
        return s
    return near_scene(facts, "waterpark", "17:00", "child", "Аквапарк недалеко", limit=20, stop="kids")


def crib(facts):
    f = _site(facts, "crib")
    if not f or not f["value"].get("crib"):
        return None
    c = f["value"]["crib"]
    if c == "нет":
        return _scene("21:00", "child", "Детской кроватки нет", "По словам отеля. Уточните при брони", False, [f])
    title = {"бесплатно": "Детская кроватка бесплатно", "за доплату": "Детская кроватка за доплату"}.get(c, "Детская кроватка есть")
    ask = "Закажите заранее, при брони" if f["value"].get("preorder") == "нужно" else "Попросите при брони"
    return _scene("21:00", "child", title, f"По словам отеля. {ask}", True, [f])


def _climate(h, month):
    """Погода и вода в месяц поездки — из фичи climate, когда она есть (бриф 4)."""
    try:
        from features.climate.backend import climate
    except Exception:  # noqa: BLE001 — фичи ещё нет или она сломана: лента живёт без неё
        return None
    try:
        return climate(h["lat"], h["lon"], month)
    except Exception:  # noqa: BLE001 — чужая фича не должна ронять ленту
        return None


def _beach_stop(h, water_note):
    """Куда именно выходим к морю — конец того же пути, что в факте beach_route. На пляже — до 13:00."""
    from core.walk import to_beach
    r = to_beach(h["lat"], h["lon"])
    if not r or not r["coords"]:
        return None
    lon, lat = r["coords"][-1]
    return _stop("beach", {"name": "Пляж", "lat": lat, "lon": lon}, "10:00", 180, "до пляжа",
                 {"title": "На пляже до обеда", "note": water_note or "Купаться и загорать"})


def beach(facts, h, month, kids):
    """Сцены пляжа: туда (10:00) и обратно (13:00)."""
    route = next((f for f in facts if f["characteristic"] == "beach_route"), None)
    straight = next((f for f in facts if f["characteristic"] == "beach_distance"), None)
    # отель у самой воды, а маршрут по графу вышел длинным — граф не дошёл до пляжа рядом;
    # верим замеру по карте (inbox 26.10: «Чайка»)
    if route and straight and straight["value"]["meters"] <= 150 and route["value"]["minutes"] > straight["value"]["walk_min"] + 10:
        route = None
    cl = _climate(h, month)
    water = cl.get("water") if isinstance(cl, dict) else None
    water_note = f"Вода в {MONTH_IN[month]} около {round(water)}°" if isinstance(water, (int, float)) else ""
    out = []
    if route:
        v = route["value"]
        down = f"под горку {v['down_m']} м" if v["down_m"] >= 10 else "почти ровно"
        notes = [down] + [s for s in (v["steps"] and "лестницы", v["underpass"] and "подземный переход",
                                      v["rail"] and "переход через железную дорогу") if s]
        title = "Пляж в паре минут" if v["minutes"] <= 2 else f"На пляж {_min(v['minutes'])} пешком"
        out.append(_scene("10:00", "beach", title,
                          ". ".join(x for x in ((", ".join(notes)).capitalize(), water_note) if x),
                          v["minutes"] <= 15, [route], _beach_stop(h, water_note)))
        climb = v.get("climb_back_m", v["up_m"])
        stairs = v["steps"] or v["underpass"] or v["bridge"]
        if kids and (climb >= KIDS_CLIMB or stairs):
            why = f"подъём {climb} м" if climb >= KIDS_CLIMB else ""
            why = ", ".join(x for x in (why, stairs and "есть лестницы") if x)
            out.append(_scene("13:00", "child", f"Обратно {_min(v['back_minutes'])}, с коляской тяжело",
                              why.capitalize(), False, [route]))
        elif climb >= 25:
            out.append(_scene("13:00", "mountain", f"Обратно {_min(v['back_minutes'])} в гору",
                              f"Подъём {climb} м, будто на {round(climb / FLOOR_M)}-й этаж по лестнице", False, [route]))
        elif climb >= 10:
            out.append(_scene("13:00", "mountain", f"Обратно {_min(v['back_minutes'])}",
                              f"Небольшой подъём, {climb} м", v["back_minutes"] <= 15, [route]))
        else:
            out.append(_scene("13:00", "check", f"Обратно {_min(v['back_minutes'])}, почти ровно",
                              "Легко зайти в номер на обед", True, [route]))
    elif straight:
        v = straight["value"]
        dist = f"{v['meters']} м" if v["meters"] < 1000 else f"{v['meters'] / 1000:.1f} км".replace(".", ",")
        title = "Море прямо у отеля" if v["meters"] <= 150 else f"До пляжа {dist}"
        walk = "Минута пешком" if v["walk_min"] <= 1 else f"{_min(v['walk_min'])} пешком".capitalize()
        out.append(_scene("10:00", "beach", title,
                          ". ".join(x for x in (walk, water_note) if x),
                          v["walk_min"] <= 15, [straight]))
    if len(out) == 2:
        out[1]["with"] = "beach"   # справка «обратно»: не нужна, когда в ленте есть путь с пляжа
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
        return _scene(s["sunset_astro"], "sunset", "Закат над морем из окна",
                      "Солнце сядет прямо в море, ничего не заслонит", True, fs)
    if s["hidden_by"] == "aside":   # далеко сбоку от оси окна (features/okno export_seed: ASIDE_DEG)
        where = "слева" if s.get("side") == "left" else "справа"
        return _scene(s["sunset_astro"], "sunset", "Закат сбоку от окна",
                      f"Солнце сядет далеко {where}, видно только у самого стекла", False, fs)
    if s["sun_hidden_at"] and s["minutes_earlier"] <= 3:
        return _scene(s["sunset_astro"], "sunset", "Закат виден из окна",
                      "Солнце уйдёт за дальние дома у самого горизонта", True, fs)
    if s["sun_hidden_at"] and s["hidden_by"] in ("building", "terrain"):
        what = "соседний дом" if s["hidden_by"] == "building" else "склон"
        return _scene(s["sun_hidden_at"], "sunset", f"Закат закроет {what}",
                      f"На {_min(s['minutes_earlier'])} раньше настоящего заката в {s['sunset_astro']}", False, fs)
    vp = next((f for f in facts if f["characteristic"] == "near:viewpoint" and f["value"].get("meters") is not None
               and f["value"]["walk_min"] <= NEAR_OK), None)
    note = (f"Смотреть его лучше со смотровой {_quote(vp['value']['name'])}, {_min_in(vp['value']['walk_min'])}"
            if vp and vp["value"].get("name") else "Солнце садится с другой стороны здания")
    st = None
    if vp:
        at = _hm(_t(s["sunset_astro"]) - 20)
        st = _stop("sunset", vp["value"], at, 30, "до смотровой",
                   {"title": "Закат со смотровой", "note": _quote(vp["value"].get("name")) or "Смотровая площадка"})
    return _scene(s["sunset_astro"], "sunset", "Заката из окна не видно", note, False, fs + ([vp] if vp else []), st)


def _like(db):
    """Тишина ночью без децибелов — на что похоже."""
    return "как в тихой комнате" if db <= 40 else "как в тихом дворе"


def night(facts, side):
    f = _pick_side(facts, "noise", side)
    if not f:
        return None
    v = f["value"]
    src = v.get("source") or {}
    if v["level"] == "quiet":
        return _scene("23:00", "moon", "Ночью тихо", f"Улицу не слышно, {_like(v['night_db'])}", True, [f])
    if v["level"] == "calm":
        return _scene("23:00", "moon", "Ночью спокойно", "Улицу почти не слышно", True, [f])
    kind, name = src.get("kind"), src.get("name")
    what = {"runway": "Слышны самолёты", "rail": "Слышны поезда"}.get(kind) or (
        f"Рядом {src.get('kind_ru', 'бар')} {_quote(name)}" if kind in ("bar", "pub", "nightclub")
        else f"Рядом {name}" if name else f"Рядом {src.get('kind_ru', 'улица')}")
    note = what.strip()                      # «Ночью шумно» уже в заголовке
    quieter = [x for x in facts if x["characteristic"] == "noise" and _scope_side(x)
               and x["value"]["level"] in ("quiet", "calm")]
    if quieter and _scope_side(f):
        best = min(quieter, key=lambda x: x["value"]["night_db"])
        note += f". Окна {SIDE_TO[_scope_side(best)]} тише"
        return _scene("23:00", "volume", "Ночью шумно", note, False, [f, best])
    return _scene("23:00", "volume", "Ночью шумно", note + ". Пригодятся беруши", False, [f])


def _airport(h):
    """Первая сцена — прилёт, когда готова фича airport (бриф 5)."""
    try:
        from features.airport.backend import arrival
    except Exception:  # noqa: BLE001 — фичи ещё нет или она сломана: лента живёт без неё
        return None
    try:
        s = arrival(h)
    except Exception:  # noqa: BLE001
        return None
    # сцена должна быть по контракту ленты, иначе лучше без неё
    if not isinstance(s, dict) or not all(isinstance(s.get(k), str) for k in ("time", "title")) or not s.get("facts"):
        return None
    return {"icon": "clock", "note": "", "good": True, "fact_ids": [f["id"] for f in s["facts"]], **s}


def _t(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _hm(minutes):
    minutes = max(0, min(int(minutes), 24 * 60 - 1))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


CHAIN = 60  # минут свободного времени, при которых идём к следующему месту сразу, не заходя в отель
WALK_SOURCE = "computed:walk-graph"


def _walk_fact(hotel_id, a, b, r):
    return {"id": f"{hotel_id}:walk:{a['id']}-{b['id']}", "hotel_id": hotel_id, "scope": "hotel",
            "characteristic": "walk_leg", "value": {k: r[k] for k in ("minutes", "meters", "up_m", "down_m")},
            "confidence": 0.7, "source": WALK_SOURCE, "method_version": "walk-graph@0.1",
            "evidence": {"from": a["name"], "to": b["name"]}, "obtained_at": dt.date.today().isoformat(),
            "valid_until": None, "status": "active"}


def _walk_row(hotel_id, a, b, r, depart, kids, outing):
    """Строка пути в ленте: когда выходим, сколько идти и что по дороге (подъём, лестницы)."""
    up, down, f = r["up_m"], r["down_m"], r["flags"]
    home = b["id"] == "hotel"
    title = f"{_min(r['minutes'])} обратно в отель" if home else f"{_min(r['minutes'])} пешком {b['to']}"
    stairs = f.get("steps") or f.get("underpass") or f.get("bridge")
    bits = []
    if up >= 25:
        bits.append(f"в гору {up} м, как подняться на {round(up / FLOOR_M)}-й этаж")
    elif up >= 10:
        bits.append(f"небольшой подъём, {up} м")
    elif down >= 10:
        bits.append(f"под горку {down} м")
    else:
        bits.append("почти ровно")
    bits += [x for x in (f.get("steps") and "есть лестницы", f.get("underpass") and "подземный переход",
                         f.get("rail") and "переход через железную дорогу") if x]
    if kids and (up >= KIDS_CLIMB or stairs):
        bits.append("с коляской тяжело")
    arrive = _hm(_t(depart) + r["minutes"])
    note = ", ".join(bits).capitalize() + (f". В отеле в {arrive}" if home else "")
    good = up < 25 and not (kids and (up >= KIDS_CLIMB or stairs))
    return {"kind": "walk", "time": depart, "icon": "pin", "title": title, "note": note, "good": good,
            "outing": outing, "to": b["id"], "minutes": r["minutes"], "arrive": arrive,
            "fact_ids": [], "facts": [_walk_fact(hotel_id, a, b, r)]}


def _outings(hotel_id, h, scenes, skip, kids):
    """Выходы из отеля по местам ленты (кроме skip): строки пути, отметки «здесь до …» и линии для карты."""
    from core.walk import route as walk
    home = {"id": "hotel", "name": h["name"], "lat": h["lat"], "lon": h["lon"], "to": "в отель"}
    places = sorted((s for s in scenes if s.get("stop") and s["stop"]["id"] not in skip), key=lambda s: s["stop"]["at"])
    rows, outings = [], []
    cur, end, out = home, None, None

    def go(a, b, depart):
        r = walk(a["lat"], a["lon"], b["lat"], b["lon"])
        if r is None:
            return None
        rows.append(_walk_row(hotel_id, a, b, r, _hm(depart), kids, len(outings)))
        out["legs"].append({"from": a["id"], "to": b["id"], "minutes": r["minutes"], "meters": r["meters"],
                            "up_m": r["up_m"], "down_m": r["down_m"]})
        out["coords"] += r["coords"] if not out["coords"] else r["coords"][1:]
        return r

    def close():
        nonlocal cur
        if out and cur is not home and go(cur, home, end):
            out["back"] = rows[-1]["arrive"]
        cur = home

    for s in places:
        st = s["stop"]
        at = _t(st["at"])
        if cur is not home:
            r = walk(cur["lat"], cur["lon"], st["lat"], st["lon"])
            if r is None or at - (end + r["minutes"]) > CHAIN:
                close()
        if cur is home:
            r0 = walk(home["lat"], home["lon"], st["lat"], st["lon"])
            if r0 is None:   # до места нет пешего пути по графу — оставляем справкой, без прямых линий
                continue
            out = {"n": len(outings) + 1, "depart": _hm(at - r0["minutes"]), "legs": [], "coords": [], "stops": []}
            outings.append(out)
            go(home, st, at - r0["minutes"])
            arrive = at
        else:
            go(cur, st, end)
            arrive = end + rows[-1]["minutes"]
        until = max(_t("13:00"), arrive + 30) if st["id"] == "beach" else arrive + st["stay"]
        s["visit"] = {"arrive": _hm(arrive), "until": _hm(until), "outing": out["n"]}
        out["stops"].append(st["id"])
        cur, end = st, until
    close()
    n = 0
    for s in sorted(places, key=lambda s: s["stop"]["at"]):
        if "visit" in s:
            n += 1
            s["visit"]["n"] = n
    for o in outings:
        o["minutes"] = sum(x["minutes"] for x in o["legs"])
        o["meters"] = sum(x["meters"] for x in o["legs"])
        o["up_m"] = sum(x["up_m"] for x in o["legs"])
        dep = _t(o["depart"])
        o["name"] = "Утром" if dep < 12 * 60 else "Днём" if dep < 17 * 60 else "Вечером" if dep < 22 * 60 else "Ночью"
    return rows, outings


def _trip(h, facts, month, interests, variant, pins):
    """День по интересам гостя (features/trip_plan): сцены мест, что они заменяют в обычной ленте, трасса."""
    if not interests:
        return None
    try:
        from features.trip_plan.backend import plan
    except Exception:  # noqa: BLE001 — фичи нет: обычная лента
        return None
    return plan(h, facts, month, interests, variant, pins)


def day(hotel_id: str, month: int, facade: str | None = None, floor: int | None = None, mode: str | None = None,
        skip=frozenset(), interests=(), variant=0, pins=None):
    """Лента дня (для API): выходы — без линий, линии отдаёт route()."""
    d = _day(hotel_id, month, facade, floor, mode, skip, interests, variant, pins)
    if d:
        d["outings"] = [{k: v for k, v in o.items() if k != "coords"} for o in d["outings"]]
    return d


def _day(hotel_id, month, facade=None, floor=None, mode=None, skip=frozenset(), interests=(), variant=0, pins=None):
    h = hotel(hotel_id)
    if h is None:
        return None
    facts = facts_for(hotel_id)
    trip = _trip(h, facts, month, interests, variant, pins)
    off = set(trip["replaces"]) if trip else set()   # что в ленте заменили места по интересам
    kids = mode == "kids" or bool(trip and trip["kids"])
    d, side, fl = _window(hotel_id, facade, floor)
    side = side or facade
    scenes = [_airport(h)]
    if d:
        scenes.append(morning(hotel_id, d, side, fl, month))
    scenes.append(breakfast(hotel_id, facts))
    if "beach" not in off:
        scenes += beach(facts, h, month, kids)
    if "pool" not in off:
        scenes.append(pool(facts))
    if kids:
        scenes += [None if "kids_afternoon" in off else kids_afternoon(facts), crib(facts)]
    if d:
        scenes.append(evening(hotel_id, d, side, fl, month, facts))
    if "dinner" not in off:
        scenes.append(dinner(facts))
    if trip:
        scenes += trip["scenes"]
    scenes.append(night(facts, side))
    scenes.append(near_scene(facts, "pharmacy_24", "23:30", "cross", "Круглосуточная аптека рядом", stop="night")
                  or near_scene(facts, "grocery_24", "23:30", "cart", "Магазин рядом работает ночью", stop="night"))
    scenes = [s for s in scenes if s]
    rows, outings = _outings(hotel_id, h, scenes, set(skip), kids)
    for s in scenes:   # гость на месте: время прихода и что там, а не «в 4 минутах»
        if "visit" in s:
            s["time"], s["title"], s["note"] = s["visit"]["arrive"], s["stop"]["here"]["title"], s["stop"]["here"]["note"]
            s["good"] = True   # трудности дороги — в строках пути, само место — хорошее
    gone = {s["with"] for s in scenes if s.get("with")} & {s["stop"]["id"] for s in scenes if "visit" in s}
    scenes = [s for s in scenes if s.get("with") not in gone] + rows
    # строка пути идёт перед местом, куда ведёт (вышли в 08:26 → кофе в 08:30)
    scenes.sort(key=lambda s: (s["time"], 0 if s.get("kind") == "walk" else 1))
    for s in scenes:
        if s.get("stop"):
            s["stop"] = {k: s["stop"][k] for k in ("id", "name", "lat", "lon")}
    walk_total = {"outings": len(outings), "minutes": sum(o["minutes"] for o in outings),
                  "meters": sum(o["meters"] for o in outings), "up_m": sum(o["up_m"] for o in outings)}
    return {"hotel_id": hotel_id, "month": month, "facade": side if d else None, "floor": fl,
            "mode": "kids" if kids else None, "scenes": scenes, "skip": sorted(skip), "walk": walk_total,
            "outings": outings, "built_at": dt.date.today().isoformat(),
            "plan": trip and {k: trip[k] for k in ("interests", "trace", "variants")} | {"variant": variant}}


# ---------- маршрут дня на карте ----------

def route(hotel_id: str, month: int, facade: str | None = None, floor: int | None = None,
          mode: str | None = None, skip=frozenset(), interests=(), variant=0, pins=None):
    """Выходы из отеля для карты: по линии на выход, остановки с номерами, итог за день."""
    d = _day(hotel_id, month, facade, floor, mode, skip, interests, variant, pins)
    if d is None:
        return None
    stops = sorted(({**s["stop"], "n": s["visit"]["n"], "time": s["visit"]["arrive"], "outing": s["visit"]["outing"]}
                    for s in d["scenes"] if s.get("visit")), key=lambda x: x["n"])
    return {"hotel_id": hotel_id, "title": "Маршрут дня", "stops": stops, "skipped": d["skip"],
            "outings": [{k: o[k] for k in ("n", "name", "depart", "back", "minutes", "meters", "up_m", "stops") if k in o}
                        for o in d["outings"]],
            "lines": [o["coords"] for o in d["outings"] if o["coords"]],
            **{k: v for k, v in d["walk"].items() if k != "outings"}}
