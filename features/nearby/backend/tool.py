"""Инструмент «что рядом»: один на все фильтры.

Фильтр — это описание (features/nearby/specs.json): какие объекты OSM считаются подходящими,
сколько минут пешком — «рядом», сколько — «можно дойти». По описанию инструмент находит
ближайший объект у каждого отеля и пишет факт near:<id> с источником, уверенностью и датой.
Новый фильтр — новая запись в specs.json, без нового кода.

Время пешком — по пешеходному графу (data/seed/poi_walk.json.gz, считает pipeline/walk_times.py):
реальный путь по улицам и лестницам с подъёмом. Если для отеля графа нет — по прямой ×1,3.
Считаем при старте сервиса (≈1 с на все фильтры), без numpy — в образе только FastAPI.
"""
import datetime as dt
import gzip
import json
import math
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from core.config import SEED
from core.seed import load
from features.hotels.backend import hotels

SPECS = Path(__file__).resolve().parents[1] / "specs.json"
DETOUR = 1.3        # пеший путь в городе длиннее прямой примерно на треть (как в beach_route)
WALK_M_MIN = 75     # ~4,5 км/ч
CELL = 400          # сетка для быстрого поиска соседей, метры
LAT0 = 43.58
M_LAT, M_LON = 110_540, 111_320 * math.cos(math.radians(LAT0))


def _xy(lat, lon):
    return lon * M_LON, lat * M_LAT


def min_to_m(minutes):
    return minutes * WALK_M_MIN / DETOUR


@lru_cache(maxsize=1)
def specs() -> list[dict]:
    return json.load(open(SPECS, encoding="utf-8"))


@lru_cache(maxsize=1)
def _poi():
    d = load("poi.json") or {"obtained_at": None, "items": []}
    return d["obtained_at"], d["items"]


@lru_cache(maxsize=1)
def _walk():
    """{hotel_id: {тег: [(секунды, индекс места), …] по возрастанию}} из графа, или {} если его нет."""
    path = SEED / "poi_walk.json.gz"
    if not path.exists():
        return {}
    _, items = _poi()
    with gzip.open(path, "rt", encoding="utf-8") as f:
        raw = json.load(f)
    out = {}
    for hid, row in raw.items():
        by_tag = defaultdict(list)
        for k in range(0, len(row), 2):
            i, sec = row[k], row[k + 1]
            by_tag[items[i][2]].append((sec, i))
        for v in by_tag.values():
            v.sort()
        out[hid] = by_tag
    return out


def _by_graph(hotel_id, spec):
    """Места фильтра по времени пешком по графу: [(секунды, индекс)] в пределах partial_min, или None."""
    walk = _walk().get(hotel_id)
    if walk is None:
        return None
    _, items = _poi()
    limit = spec["partial_min"] * 60
    found = [(sec, i) for tag in spec["osm"] for sec, i in walk.get(tag, ())
             if sec <= limit and (not spec.get("night") or items[i][4])]
    return sorted(found)


def _meters(h, it):
    x, y = _xy(h["lat"], h["lon"])
    x2, y2 = _xy(it[0], it[1])
    return round(math.hypot(x - x2, y - y2))


def _grid(items):
    g = defaultdict(list)
    for it in items:
        x, y = _xy(it[0], it[1])
        g[(int(x // CELL), int(y // CELL))].append((x, y, it))
    return g


def compute(spec: dict) -> list[dict]:
    """Факты near:<id> для всех отелей по одному описанию фильтра."""
    obtained, items = _poi()
    tags = set(spec["osm"])
    chosen = [it for it in items if it[2] in tags and (not spec.get("night") or it[4])]
    grid = _grid(chosen)
    radius = min_to_m(spec["partial_min"])
    reach = int(radius // CELL) + 1
    today = dt.date.today()
    obtained_at = obtained or today.isoformat()
    out = []
    for h in hotels():
        g = _by_graph(h["id"], spec)
        if g is not None:
            # по графу: ближайшее по времени, а не по прямой
            if g:
                sec, i = g[0]
                it = items[i]
                value = {"meters": _meters(h, it), "walk_min": max(1, round(sec / 60)), "name": it[3],
                         "kind": spec["kind"], "lat": it[0], "lon": it[1], "count": len(g)}
                conf, evidence = 0.8, {"osm": it[5], "tag": it[2]}
            else:
                value = {"meters": None, "within_min": spec["partial_min"], "kind": spec["kind"], "count": 0}
                conf, evidence = 0.5, {}
            out.append(_fact(h, spec, value, conf, evidence, obtained_at, today,
                             "пешеходный граф OSM, время по Тоблеру"))
            continue
        hx, hy = _xy(h["lat"], h["lon"])
        cx, cy = int(hx // CELL), int(hy // CELL)
        best, count = None, 0
        for i in range(cx - reach, cx + reach + 1):
            for j in range(cy - reach, cy + reach + 1):
                for x, y, it in grid.get((i, j), ()):
                    d = math.hypot(x - hx, y - hy)
                    if d <= radius:
                        count += 1
                        if best is None or d < best[0]:
                            best = (d, it)
        if best:
            d, it = best
            value = {"meters": round(d), "walk_min": max(1, round(d * DETOUR / WALK_M_MIN)),
                     "name": it[3], "kind": spec["kind"], "lat": it[0], "lon": it[1], "count": count}
            conf, evidence = 0.75, {"osm": it[5], "tag": it[2]}
        else:
            # не нашли — это «на карте не нашли», а не «точно нет»: маленькие магазины OSM знает не все
            value = {"meters": None, "within_min": spec["partial_min"], "kind": spec["kind"], "count": 0}
            conf, evidence = 0.45, {}
        out.append(_fact(h, spec, value, conf, evidence, obtained_at, today, f"по прямой ×{DETOUR}, {WALK_M_MIN} м/мин"))
    return out


def _fact(h, spec, value, conf, evidence, obtained_at, today, method):
    graph = method.startswith("пешеходный")
    return {
        "id": f"{h['id']}:near:{spec['id']}:hotel", "hotel_id": h["id"], "scope": "hotel",
        "characteristic": f"near:{spec['id']}", "value": value, "confidence": conf,
        "source": "computed:osm-poi+walk" if graph else "computed:osm-poi",
        "method_version": "nearby-walk@0.2" if graph else "nearby@0.1",
        "evidence": {**evidence, "spec": spec["id"], "method": method},
        "obtained_at": obtained_at, "valid_until": (today + dt.timedelta(days=180)).isoformat(),
        "status": "active",
    }


def places(hotel: dict, spec: dict, limit: int = 40) -> list[dict]:
    """Все места этого типа в пешей доступности отеля — для показа на карте по клику."""
    _, items = _poi()
    g = _by_graph(hotel["id"], spec)
    if g is not None:
        return [{"name": items[i][3], "kind": spec["kind"], "lat": items[i][0], "lon": items[i][1],
                 "osm": items[i][5], "meters": _meters(hotel, items[i]), "walk_min": max(1, round(sec / 60))}
                for sec, i in g[:limit]]
    tags = set(spec["osm"])
    radius = min_to_m(spec["partial_min"])
    hx, hy = _xy(hotel["lat"], hotel["lon"])
    out = []
    for it in items:
        if it[2] not in tags or (spec.get("night") and not it[4]):
            continue
        x, y = _xy(it[0], it[1])
        d = math.hypot(x - hx, y - hy)
        if d <= radius:
            out.append({"name": it[3], "kind": spec["kind"], "lat": it[0], "lon": it[1], "osm": it[5],
                        "meters": round(d), "walk_min": max(1, round(d * DETOUR / WALK_M_MIN))})
    return sorted(out, key=lambda p: p["meters"])[:limit]


def all_nearby_facts() -> list[dict]:
    return [f for s in specs() for f in compute(s)]
