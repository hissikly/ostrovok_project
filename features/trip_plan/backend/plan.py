"""Агент-планировщик дня по интересам гостя.

Гость отметил, чем хочет заняться (плавать, культура, тусить…). Для отеля агент:
  1. ставит каждый интерес в своё время суток (плавать — утром, тусить — ночью);
  2. ищет места-кандидаты: что рядом пешком по графу улиц (features/nearby), пляж (core.walk);
  3. проверяет каждого: открыто ли в это время (часы OSM), дойти ли пешком, тихо ли ночью у окон;
  4. из прошедших проверку выбирает одно — в варианте 0 лучшее, в следующих — другие по очереди;
     закреплённое гостем не меняет; иногда добавляет «сюрприз» не из интересов;
  5. вставляет обед рядом со следующим местом, если между пляжем и дневным местом есть окно;
  6. пишет трассу — каждое решение и откуда данные.
Факты (место, время пешком, часы) дают только инструменты; LLM здесь не нужен.

Сцены — в формате ленты features/day: {time, icon, title, note, good, fact_ids, facts, stop?}
+ interest, interest_title, place, alts. stop — как в day: {id, name, lat, lon, at, stay, to, here}.
"""
import datetime as dt
import math
import random
import re
from functools import lru_cache

from core.seed import load
from features.trip_plan.backend.hours import closes, is_open
from features.trip_plan.backend.interests import BY_ID, KIND, ORDER

LIMIT = 15        # минут пешком — «рядом», дальше не ведём
TOP = 4           # сколько лучших мест одного интереса участвуют в вариантах
LUNCH_NEAR_M = 400
LUNCH_STAY = 60
WEEKDAY = 5       # день для проверки часов: суббота — в выходной закрыто больше всего мест
QUIET_BAR_MIN = 5  # «выспаться» + «тусить»: бар не ближе стольких минут от окон
SURPRISE_SPECS = ("viewpoint", "sights", "zoo", "park")
SPORT_POOL = re.compile(r"^Бассейн\s*№")  # нумерованные бассейны в OSM — спортивные, не для гостя


def _t(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _hm(m):
    m = max(0, min(int(m), 24 * 60 - 1))
    return f"{m // 60:02d}:{m % 60:02d}"


def _plural(n, one, few, many):
    n = abs(n) % 100
    if 11 <= n <= 14:
        return many
    return {1: one, 2: few, 3: few, 4: few}.get(n % 10, many)


def _q(name):
    return name if any(c in name for c in "«\"„“") else f"«{name}»"


@lru_cache(maxsize=1)
def _poi_tags():
    d = load("poi.json") or {"items": []}
    return {it[5]: it[2] for it in d["items"]}


@lru_cache(maxsize=1)
def _poi_items():
    return (load("poi.json") or {"items": []})["items"]


def _places(h, spec_id, within=LIMIT):
    """Места фильтра «рядом» у отеля по графу улиц (features/nearby), в within минутах: ближайшие первыми."""
    from features.nearby.backend import places, specs
    spec = next((s for s in specs() if s["id"] == spec_id), None)
    if not spec:
        return []
    tags = _poi_tags()
    # у фильтра «рядом» свой радиус (бар — 10 минут); для дня ищем дальше — до within
    spec = {**spec, "partial_min": max(spec["partial_min"], within)}
    return [{**p, "tag": tags.get(p["osm"], "")} for p in places(h, spec)]


def _fact(hotel_id, interest, p, obtained):
    return {"id": f"{hotel_id}:trip:{interest}:{p['osm']}", "hotel_id": hotel_id, "scope": "hotel",
            "characteristic": "trip_place", "value": {k: p.get(k) for k in ("name", "walk_min", "meters", "lat", "lon")},
            "confidence": 0.8 if p.get("graph", True) else 0.7, "source": "computed:osm-poi+walk",
            "method_version": "trip-plan@0.1",
            "evidence": {"osm": p["osm"], "tag": p.get("tag"), "hours": p.get("hours")},
            "obtained_at": obtained, "valid_until": None, "status": "active"}


def _label(p):
    kind, _ = KIND.get(p.get("tag"), ("Место", "до места"))
    return kind


def _candidates(h, it, slot, quiet):
    """Места интереса, прошедшие проверки, и отсеянные с причиной: (годные, отсеянные)."""
    good, dropped, seen = [], [], set()
    for spec in it["specs"]:
        for p in _places(h, spec, it.get("limit", LIMIT)):
            if p["osm"] in seen or p["walk_min"] > it.get("limit", LIMIT):
                continue
            seen.add(p["osm"])
            if (it.get("named") and not p["name"]) or SPORT_POOL.match(p["name"] or ""):
                continue
            p["name"] = p["name"] or _label(p)
            op = is_open(p["osm"], WEEKDAY, slot, it["stay"])
            if op is False:
                dropped.append((p, "closed"))
                continue
            if quiet and it["id"] == "party" and p["walk_min"] < QUIET_BAR_MIN:
                dropped.append((p, "quiet"))
                continue
            p["open"] = op
            good.append(p)
    # ближе — лучше; места без часов работы — чуть хуже, чем точно открытые
    good.sort(key=lambda p: p["walk_min"] + (3 if p["open"] is None else 0))
    return good, dropped


def _beach(h):
    from core.walk import to_beach
    r = to_beach(h["lat"], h["lon"])
    if not r or not r["coords"]:
        return None
    lon, lat = r["coords"][-1]
    return {"name": "Пляж", "lat": lat, "lon": lon, "walk_min": r["minutes"], "meters": r.get("meters"),
            "osm": "beach", "tag": "beach", "open": True}


def _sea(h, facts, month):
    """Кандидаты «плавать»: пляж, бассейн отеля (по словам отеля), бассейн или аквапарк рядом."""
    out = []
    b = _beach(h)
    if b and b["walk_min"] <= 25:
        out.append(b)
    pool = next((f for f in facts if f["characteristic"] == "web:pool" and f["value"].get("pool") == "есть"), None)
    if pool:
        heated = pool["value"].get("heated")
        out.append({"name": "Бассейн отеля", "osm": "hotel_pool", "tag": "hotel_pool", "walk_min": 0,
                    "open": True, "heated": heated, "fact": pool})
    for spec in ("waterpark",):
        for p in _places(h, spec):
            if p["walk_min"] <= 20 and not SPORT_POOL.match(p["name"] or ""):
                p["name"] = p["name"] or _label(p)
                p["open"] = is_open(p["osm"], WEEKDAY, _t("11:00"), 120)
                if p["open"] is not False:
                    out.append(p)
    return out


def _water(h, month):
    try:
        from features.climate.backend import climate
        w = climate(h["lat"], h["lon"], month).get("water")
        return w if isinstance(w, (int, float)) else None
    except Exception:  # noqa: BLE001 — фичи погоды может не быть: план живёт без неё
        return None


def _order(cands, seed):
    """Порядок вариантов: лучшее первым, остальные из TOP — в перемешанном, но постоянном для отеля порядке."""
    if len(cands) <= 1:
        return cands
    head, tail = cands[:1], cands[1:TOP]
    random.Random(seed).shuffle(tail)
    return head + tail


def _note(it, p, weekday=WEEKDAY):
    if p["tag"] == "hotel_pool":
        return ("С подогревом, по словам отеля" if p.get("heated") else "По словам отеля")
    if p["tag"] == "beach":
        return "Купаться и загорать"
    kind = _label(p)
    c = closes(p["osm"], weekday) if p["osm"] not in ("beach", "hotel_pool") else None
    hours = f"открыто {c}" if c and c != "круглосуточно" else "круглосуточно" if c else "часы работы не указаны"
    return f"{kind}, {hours}" if kind.lower() not in p["name"].lower() else hours.capitalize()


def _scene(hotel_id, it, p, slot, obtained, alts, pinned):
    kind, to = KIND.get(p["tag"], ("Место", "до места"))
    title = p["name"] if p["tag"] in ("beach", "hotel_pool") else _q(p["name"])
    fact = p.get("fact") or _fact(hotel_id, it["id"], p, obtained)
    s = {"time": _hm(slot), "icon": it["icon"], "title": title, "note": _note(it, p), "good": True,
         "fact_ids": [fact["id"]], "facts": [fact], "interest": it["id"], "interest_title": it["title"],
         "place": p["osm"], "alts": alts, "pinned": pinned}
    if p["tag"] != "hotel_pool" and p.get("lat") is not None:
        stay = 180 if p["tag"] == "beach" else it["stay"]
        s["stop"] = {"id": f"i:{it['id']}", "name": p["name"], "lat": p["lat"], "lon": p["lon"],
                     "at": _hm(slot), "stay": stay, "to": to, "here": {"title": title, "note": s["note"]}}
    return s


def _near_point(items_tags, lat, lon, slot, stay, exclude=()):
    """Места нужных типов в LUNCH_NEAR_M по прямой от точки, открытые в это время: [(метры, место)] ближайшие первыми."""
    m_lat, m_lon = 111_320, 111_320 * math.cos(math.radians(lat))
    out = []
    for it in _poi_items():
        if it[2] not in items_tags or not it[3] or it[5] in exclude:
            continue
        d = math.hypot((it[0] - lat) * m_lat, (it[1] - lon) * m_lon)
        if d <= LUNCH_NEAR_M and is_open(it[5], WEEKDAY, slot, stay) is not False:
            out.append((d, it))
    return sorted(out, key=lambda x: x[0])


def plan(h, facts, month, interests, variant=0, pins=None):
    """План дня для отеля: сцены интересов, что они заменяют в обычной ленте, трасса, сколько вариантов."""
    pins = pins or {}
    hid = h["id"]
    obtained = (load("poi.json") or {}).get("obtained_at") or dt.date.today().isoformat()
    picked = [i for i in ORDER if i in interests]
    quiet = "quiet" in picked
    scenes, trace, replaces = [], [], set()
    combos = 1
    used, no_hours = set(), []
    trace.append({"kind": "look", "text": "Взяли отмеченные интересы и поставили каждый в своё время дня",
                  "source": ", ".join(BY_ID[i]["title"].lower() for i in picked)})
    for iid in picked:
        it = BY_ID[iid]
        if iid == "quiet":
            continue   # тишину ночью показывает обычная лента — сцена «Ночью тихо/шумно»
        slot = _t(it["slot"])
        if iid == "sea":
            cands, dropped = _sea(h, facts, month), []
            w = _water(h, month)
            if w is not None and w < 20 and any(c["tag"] in ("hotel_pool", "leisure=swimming_pool", "leisure=water_park") for c in cands):
                cands.sort(key=lambda c: 0 if c["tag"] != "beach" else 1)
                trace.append({"kind": "swap", "text": f"Вода в море около {round(w)}° — первым предлагаем бассейн",
                              "source": "температура воды по месяцам"})
            replaces |= {"beach", "pool"}
        else:
            cands, dropped = _candidates(h, it, slot, quiet)
        cands = [c for c in cands if c["osm"] not in used]
        if iid == "food":
            replaces.add("dinner")
        if iid == "kids":
            replaces.add("kids_afternoon")
        if not cands:
            trace.append({"kind": "none", "text": f"{it['title']}: {it['none']} в {LIMIT} минутах пешком на карте не нашли",
                          "source": "места OpenStreetMap, путь по улицам"})
            scenes.append({"time": it["slot"], "icon": it["icon"], "title": it["none_title"],
                           "note": f"Честно: в пределах {it.get('limit', LIMIT)} минут пешком таких мест не нашли", "good": False,
                           "fact_ids": [], "facts": [], "interest": iid, "interest_title": it["title"], "alts": 0})
            continue
        order = _order(cands, f"{hid}:{iid}")
        pin = pins.get(iid)
        chosen = next((c for c in cands if c["osm"] == pin), None) if pin else None
        if chosen is None:
            chosen = order[variant % len(order)]
            combos *= len(order)
        used.add(chosen["osm"])
        if chosen is not None and pin == chosen["osm"]:
            trace.append({"kind": "pin", "text": f"{_q(chosen['name'])} закреплено вами — не меняли", "source": ""})
        else:
            many = f"из {len(order)} {_plural(len(order), 'подходящего места', 'подходящих мест', 'подходящих мест')}" if len(order) > 1 else "единственное подходящее"
            walk = "в отеле" if chosen["walk_min"] == 0 else f"{chosen['walk_min']} мин пешком"
            trace.append({"kind": "ok", "text": f"{it['title']}: {many} — {_q(chosen['name']) if chosen['tag'] not in ('beach', 'hotel_pool') else chosen['name'].lower()}, {walk}",
                          "source": "места OpenStreetMap, путь по улицам с подъёмами" if chosen["tag"] != "hotel_pool" else "сайт отеля"})
        closed = [p for p, why in dropped if why == "closed" and p["walk_min"] < chosen["walk_min"]]
        if closed:
            trace.append({"kind": "swap", "text": f"{_q(closed[0]['name'])} ближе, но в {it['slot']} закрыто — не берём",
                          "source": "часы работы из OpenStreetMap"})
        if any(why == "quiet" for _, why in dropped):
            trace.append({"kind": "swap", "text": f"Бары ближе {QUIET_BAR_MIN} минут от отеля не берём — вы хотите выспаться",
                          "source": "ваши интересы «тусить» и «выспаться»"})
        if chosen["open"] is None and chosen["tag"] not in ("beach", "hotel_pool"):
            no_hours.append(chosen["name"])
        scenes.append(_scene(hid, it, chosen, slot, obtained, len(order), pin == chosen["osm"]))

    if no_hours:
        n = len(no_hours)
        trace.append({"kind": "none", "text": (f"У {_q(no_hours[0])} на карте нет часов работы" if n == 1 else
                                               f"У {n} мест на карте нет часов работы") + " — проверьте перед выходом",
                      "source": "OpenStreetMap"})

    # обед по пути: утром пляж, днём место — едим рядом со вторым, а не возвращаемся
    day_stops = sorted((s for s in scenes if s.get("stop")), key=lambda s: s["stop"]["at"])
    morning = [s for s in day_stops if _t(s["stop"]["at"]) < 12 * 60]
    after = [s for s in day_stops if 14 * 60 <= _t(s["stop"]["at"]) < 18 * 60]
    if morning and after and "food" not in picked:
        nxt = after[0]["stop"]
        # обедаем так, чтобы из кафе сразу идти дальше, не заходя в отель
        at = max(_t("13:15"), _t(nxt["at"]) - LUNCH_STAY - 15)
        near = _near_point({"amenity=cafe", "amenity=restaurant", "amenity=fast_food"}, nxt["lat"], nxt["lon"], at, LUNCH_STAY, used)
        if near:
            d, poi = near[variant % min(len(near), 3)]   # в других вариантах — другое кафе из трёх ближайших
            p = {"name": poi[3], "lat": poi[0], "lon": poi[1], "osm": poi[5], "tag": poi[2], "walk_min": None, "open": True}
            kind, to = KIND.get(poi[2], ("Кафе", "до кафе"))
            fact = _fact(hid, "lunch", p, obtained)
            c = closes(poi[5], WEEKDAY)
            note = f"{kind}, {round(d)} м от {after[0]['stop']['to'][3:]}" + (f", открыто {c}" if c and c != "круглосуточно" else "")
            scenes.append({"time": _hm(at), "icon": "fork", "title": f"Обед в {_q(poi[3])}", "note": note, "good": True,
                           "fact_ids": [fact["id"]], "facts": [fact], "interest": "lunch", "interest_title": "По пути",
                           "place": poi[5], "alts": 0,
                           "stop": {"id": "i:lunch", "name": poi[3], "lat": poi[0], "lon": poi[1], "at": _hm(at), "stay": LUNCH_STAY,
                                    "to": to, "here": {"title": f"Обед в {_q(poi[3])}", "note": note}}})
            trace.append({"kind": "ok", "text": f"Между пляжем и следующим местом — обед в {_q(poi[3])}, в {round(d)} м от него, а не у отеля",
                          "source": "кафе OpenStreetMap рядом с маршрутом"})

    # сюрприз: в каждом втором варианте — одно место не из интересов, если вечером до ужина есть окно
    if variant % 2 == 1:
        busy = any(16 * 60 <= _t(s["time"]) < 19 * 60 for s in scenes)
        if not busy:
            pool = []
            for spec in SURPRISE_SPECS:
                pool += [p for p in _places(h, spec) if p["name"] and p["walk_min"] <= LIMIT and p["osm"] not in used
                         and is_open(p["osm"], WEEKDAY, _t("17:00"), 60) is not False]
            if pool:
                p = random.Random(f"{hid}:surprise:{variant}").choice(pool)
                p["open"] = is_open(p["osm"], WEEKDAY, _t("17:00"), 60)
                it = {"id": "surprise", "title": "Неожиданно", "icon": "sparkle", "stay": 60}
                s = _scene(hid, it, p, _t("17:00"), obtained, 0, False)
                s["note"] = f"Не из ваших интересов, но {p['walk_min']} мин пешком. {s['note']}"
                if s.get("stop"):
                    s["stop"]["here"]["note"] = s["note"]
                scenes.append(s)
                trace.append({"kind": "surprise", "text": f"Сюрприз: {_q(p['name'])} — {_label(p).lower()} в {p['walk_min']} мин, вечером было свободное окно",
                              "source": "места OpenStreetMap"})
    # сюрприз через вариант — тоже вариант: даже когда всё остальное единственное, день можно освежить
    if combos == 1 and any(p["name"] for spec in SURPRISE_SPECS for p in _places(h, spec)):
        combos = 2
    return {"scenes": scenes, "trace": trace, "replaces": sorted(replaces), "kids": "kids" in picked,
            "variants": combos, "interests": picked}
