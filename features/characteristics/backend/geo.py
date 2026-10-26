"""Что на карте рядом с отелем — для любого тега OSM, а не только для 36 фильтров «что рядом».

Места берём из двух выгрузок: data/seed/poi.json (фильтры features/nearby) и data/seed/osm_layers.json.gz
(слои агента: всё остальное, линии точками через ~50 м, см. pipeline/extract_osm_layers.py).
Время пешком — по пешеходному графу (core/walk.py): Дейкстра от отеля до ближайшей подходящей точки,
с подъёмами и лестницами. Нет графа или отель далеко от дорог — по прямой ×1,3, как в nearby.
"""
import gzip
import json
import math
from collections import defaultdict
from functools import lru_cache

from core.config import SEED
from core.seed import load
from core.walk import SNAP_SPEED, graph

DETOUR, WALK_M_MIN = 1.3, 75
CELL = 400
LAT0 = 43.58
M_LAT, M_LON = 110_540, 111_320 * math.cos(math.radians(LAT0))


def _xy(lat, lon):
    return lon * M_LON, lat * M_LAT


@lru_cache(maxsize=1)
def layers() -> tuple[str | None, dict[str, list]]:
    """{тег: [[lat, lon, название, "way/1"], …]} из обеих выгрузок."""
    out = defaultdict(list)
    obtained = None
    path = SEED / "osm_layers.json.gz"
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as f:
            d = json.load(f)
        obtained = d["obtained_at"]
        for kv, pts in d["layers"].items():
            out[kv] = pts
    # из выгрузки «что рядом» — только теги, которых нет в слоях (иначе одно место попадёт дважды)
    poi = load("poi.json") or {"items": []}
    mine = set(out)
    for lat, lon, kv, name, _night, oid in poi["items"]:
        if kv not in mine:
            out[kv].append([lat, lon, name, oid])
    return obtained or poi.get("obtained_at"), dict(out)


def known_tags() -> dict[str, int]:
    """Какие теги вообще есть на карте вокруг отелей и сколько у каждого точек — для LLM и проверки спеки."""
    return {kv: len(v) for kv, v in layers()[1].items()}


def _grid(points):
    g = defaultdict(list)
    for p in points:
        x, y = _xy(p[0], p[1])
        g[(int(x // CELL), int(y // CELL))].append((x, y, p))
    return g


class Finder:
    """Ближайшее место из набора тегов для каждого отеля — один раз собираем сетку и привязку к графу."""

    def __init__(self, tags: list[str], within_min: int):
        lay = layers()[1]
        self.points = [p + [kv] for kv in tags for p in lay.get(kv, ())]
        self.grid = _grid(self.points)
        self.within_s = within_min * 60
        self.radius = within_min * WALK_M_MIN / DETOUR * 1.15   # по прямой не дальше, чем дойдёшь
        self.g = graph()
        self._node = {}

    def _snap(self, p):
        key = (p[0], p[1])
        if key not in self._node:
            n = self.g.nearest(p[0], p[1])
            if n is None:
                self._node[key] = None
            else:
                d = math.hypot(*(a - b for a, b in zip(_xy(self.g.lat[n], self.g.lon[n]), _xy(p[0], p[1]))))
                self._node[key] = (n, d / SNAP_SPEED)
        return self._node[key]

    def around(self, lat, lon):
        hx, hy = _xy(lat, lon)
        cx, cy = int(hx // CELL), int(hy // CELL)
        reach = int(self.radius // CELL) + 1
        for i in range(cx - reach, cx + reach + 1):
            for j in range(cy - reach, cy + reach + 1):
                for x, y, p in self.grid.get((i, j), ()):
                    d = math.hypot(x - hx, y - hy)
                    if d <= self.radius:
                        yield d, p

    def nearest(self, lat, lon) -> dict:
        """{found, meters, walk_min, name, lat, lon, osm, tag, count, by} — ближайшее по времени пешком."""
        cand = list(self.around(lat, lon))
        if not cand:
            return {"found": False, "count": 0, "by": "none"}
        objects = len({p[3] for _, p in cand})
        if self.g is not None:
            s = self.g.nearest(lat, lon)
            if s is not None:
                snap0 = math.hypot(*(a - b for a, b in zip(_xy(self.g.lat[s], self.g.lon[s]), _xy(lat, lon)))) / SNAP_SPEED
                times, _, _ = self.g.dijkstra(s, cutoff_s=self.within_s)
                best = None
                for d, p in cand:
                    sn = self._snap(p)
                    if sn is None or sn[0] not in times:
                        continue
                    t = snap0 + times[sn[0]] + sn[1]
                    if t <= self.within_s and (best is None or t < best[0]):
                        best = (t, d, p)
                if best:
                    t, d, p = best
                    return self._out(p, d, max(1, round(t / 60)), objects, "graph")
                return {"found": False, "count": 0, "by": "graph"}
        d, p = min(cand, key=lambda c: c[0])
        return self._out(p, d, max(1, round(d * DETOUR / WALK_M_MIN)), objects, "line")

    @staticmethod
    def _out(p, d, minutes, count, by):
        return {"found": True, "meters": round(d), "walk_min": minutes, "name": p[2], "lat": p[0], "lon": p[1],
                "osm": p[3], "tag": p[4], "count": count, "by": by}

    def all_near(self, lat, lon, limit=40) -> list[dict]:
        """Все объекты (по одному на объект OSM) в пешей доступности — для карты по клику."""
        seen = {}
        for d, p in sorted(self.around(lat, lon), key=lambda c: c[0]):
            if p[3] not in seen:
                seen[p[3]] = {"name": p[2], "lat": p[0], "lon": p[1], "osm": p[3], "meters": round(d),
                              "walk_min": max(1, round(d * DETOUR / WALK_M_MIN))}
        return list(seen.values())[:limit]
