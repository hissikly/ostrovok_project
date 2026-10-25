"""Линзы — то, что гость включает вместо фильтров. Каждая читает факты отеля и отвечает:
подходит / частично / нет / не знаем — с одной фразой «почему» и уверенностью факта.

Линза никогда не додумывает: нет нужного факта → «не знаем», а не «нет».
Основные линзы — ниже в LENSES; фильтры «что рядом» собираются из каталога features/nearby
(описание в specs.json → одна общая функция near), новый фильтр там появляется здесь сам.
"""
from features.nearby.backend import specs as nearby_specs
MATCH, PARTIAL, NO, UNKNOWN = "match", "partial", "no", "unknown"
SIDE = {"N": "север", "E": "восток", "S": "юг", "W": "запад"}


def _by_char(facts, char):
    return [f for f in facts if f["characteristic"] == char and f["status"] == "active"]


def _one(facts, char):
    fs = _by_char(facts, char)
    return fs[0] if fs else None


def _side(f):
    return SIDE.get(f["scope"].split(":")[-1], "")


def _res(state, text, facts):
    facts = [f for f in facts if f]
    conf = min((f["confidence"] for f in facts), default=None)
    return {"state": state, "text": text, "confidence": conf,
            "sources": sorted({f["source"] for f in facts}), "facts": [f["id"] for f in facts]}


def sea_view(facts, ctx):
    fs = _by_char(facts, "sea_view")
    if not fs:
        return _res(UNKNOWN, "Вид из окон ещё не посчитали", [])
    full = sorted((f for f in fs if f["value"]["from_floor"]), key=lambda f: f["value"]["from_floor"])
    if full:
        f = full[0]
        n = f["value"]["from_floor"]
        floor = "с любого этажа" if n == 1 else f"с {n}-го этажа"
        return _res(MATCH, f"Море из окон на {_side(f)} {floor}", [f])
    glimpse = sorted((f for f in fs if f["value"]["glimpse_from"]), key=lambda f: f["value"]["glimpse_from"])
    if glimpse:
        f = glimpse[0]
        return _res(PARTIAL, f"Море только краешком: {_side(f)}, с {f['value']['glimpse_from']}-го этажа", [f])
    return _res(NO, "Моря из окон не видно", fs)


def sunset(facts, ctx):
    fs = _by_char(facts, "sunset_view")
    if not _by_char(facts, "sea_view"):
        return _res(UNKNOWN, "Вид из окон ещё не посчитали", [])
    month = ctx.get("month")
    fit = [f for f in fs if not month or month in f["value"]["months"]]
    if fit:
        f = max(fit, key=lambda f: len(f["value"]["months"]))
        when = f" в {month_prep(month)}" if month else ""
        return _res(MATCH, f"Закат над морем{when} из окон на {_side(f)}", [f])
    if fs and month:
        return _res(NO, f"Закат над морем бывает, но не в {month_prep(month)}", fs)
    return _res(NO, "Закат над морем из окон не виден", _by_char(facts, "sea_view")[:1])


def month_prep(m):
    """«в мае», «в июне» — предложный падеж месяца."""
    return ["", "январе", "феврале", "марте", "апреле", "мае", "июне", "июле", "августе",
            "сентябре", "октябре", "ноябре", "декабре"][m]


def beach_near(facts, ctx):
    f = _one(facts, "beach_distance")
    if not f:
        return _res(UNKNOWN, "Расстояние до пляжа не знаем", [])
    m, mins = f["value"]["meters"], f["value"]["walk_min"]
    text = f"До пляжа {_dist(m)}, около {mins} мин пешком"
    if m <= 400:
        return _res(MATCH, text, [f])
    if m <= 900:
        return _res(PARTIAL, text, [f])
    return _res(NO, text, [f])


def flat(facts, ctx):
    """Обратно с пляжа в гору: пляж на уровне моря, значит подъём ≈ высота отеля над морем."""
    f = _one(facts, "elevation")
    if not f:
        return _res(UNKNOWN, "Высоту над морем не знаем", [])
    h = f["value"]["meters"]
    floors = round(h / 3)
    if h <= 15:
        return _res(MATCH, "Почти на уровне моря, с пляжа без подъёма", [f])
    if h <= 35:
        return _res(PARTIAL, f"С пляжа подъём {h} м, как на {floors}-й этаж", [f])
    return _res(NO, f"С пляжа в гору {h} м, как на {floors}-й этаж", [f])


def _dist(m):
    return f"{m} м" if m < 1000 else f"{m / 1000:.1f} км".replace(".", ",")


def near(spec):
    """Оценщик для фильтра из каталога «что рядом»."""
    char = f"near:{spec['id']}"

    def fn(facts, ctx):
        f = _one(facts, char)
        if not f:
            return _res(UNKNOWN, f"{spec['kind']}: пока не знаем", [])
        v = f["value"]
        if v["meters"] is None:
            return _res(NO, f"{spec['kind']}: на карте в {v['within_min']} мин пешком не нашли", [f])
        name = f"{v['kind']} «{v['name']}»" if v["name"] else v["kind"]
        text = f"{name} в {_dist(v['meters'])}, {v['walk_min']} мин пешком"
        state = MATCH if v["walk_min"] <= spec["match_min"] else PARTIAL
        r = _res(state, text, [f])
        r["point"] = {"lat": v["lat"], "lon": v["lon"], "name": name}
        return r
    return fn


LENSES = [
    {"id": "sea_view", "title": "Вид на море", "icon": "waves", "fn": sea_view,
     "hint": "Считаем по рельефу и соседним домам, с какого этажа видно море"},
    {"id": "sunset", "title": "Закат из окна", "icon": "sunset", "fn": sunset,
     "hint": "Где садится солнце в ваши даты и не закрыто ли оно горой или домом"},
    {"id": "beach_near", "title": "Рядом пляж", "icon": "beach", "fn": beach_near,
     "hint": "До ближайшего пляжа по карте OSM"},
    {"id": "flat", "title": "С пляжа не в гору", "icon": "mountain", "fn": flat,
     "hint": "Отель почти на уровне моря: обратно с пляжа не придётся подниматься в гору"},
]
for l in LENSES:
    l["primary"] = True
LENSES += [{"id": f"near_{s['id']}", "title": s["title"], "icon": s["icon"], "fn": near(s), "primary": False,
            "group": s["group"], "synonyms": s["synonyms"],
            "hint": f"До {s['match_min']} мин пешком — рядом, до {s['partial_min']} мин — можно дойти. По карте OSM"}
           for s in nearby_specs()]
BY_ID = {l["id"]: l for l in LENSES}
