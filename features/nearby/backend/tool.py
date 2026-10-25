"""Инструмент «что рядом»: один на все фильтры.

Фильтр — это описание (features/nearby/specs.json): какие объекты OSM считаются подходящими,
сколько минут пешком — «рядом», сколько — «можно дойти». По описанию инструмент находит
ближайший объект у каждого отеля и пишет факт near:<id> с источником, уверенностью и датой.
Новый фильтр — новая запись в specs.json, без нового кода.

Считаем при старте сервиса (≈1 с на все фильтры), без numpy — в образе только FastAPI.
"""
import datetime as dt
import json
import math
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

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
        out.append({
            "id": f"{h['id']}:near:{spec['id']}:hotel", "hotel_id": h["id"], "scope": "hotel",
            "characteristic": f"near:{spec['id']}", "value": value, "confidence": conf,
            "source": "computed:osm-poi", "method_version": "nearby@0.1",
            "evidence": {**evidence, "spec": spec["id"], "method": f"по прямой ×{DETOUR}, {WALK_M_MIN} м/мин"},
            "obtained_at": obtained_at, "valid_until": (today + dt.timedelta(days=180)).isoformat(),
            "status": "active",
        })
    return out


def all_nearby_facts() -> list[dict]:
    return [f for s in specs() for f in compute(s)]
