"""Пешие маршруты по графу Сочи (data/seed/walk_graph.json.gz, собирает features/beach_route/pipeline).

Общее для нескольких фич: путь до пляжа (beach_route), маршрут до места рядом (nearby).
Чистый Python (в образе сервиса нет numpy): A* до точки, Дейкстра до ближайшей из целей.
Время — по Тоблеру в обе стороны: «туда 7 мин вниз, обратно 11 в гору».
"""
import gzip
import heapq
import math
from functools import lru_cache

from core.config import SEED

STEPS, TUNNEL, BRIDGE, MAJOR, RAIL, FOOT = 1, 2, 4, 8, 16, 32
V_MAX = 6 / 3.6          # максимум Тоблера, м/с — для эвристики A*
LAT0 = 43.58
M_LAT, M_LON = 110_540, 111_320 * math.cos(math.radians(LAT0))
CELL = 150               # сетка для поиска ближайшего узла, м
SNAP_MAX = 400           # дальше этого от дороги — маршрута нет
SNAP_SPEED = 1.2         # м/с — от точки до ближайшей дороги


class Graph:
    def __init__(self, d):
        n = d["nodes"]
        self.lat = [n[i] / 1e5 for i in range(0, len(n), 2)]
        self.lon = [n[i] / 1e5 for i in range(1, len(n), 2)]
        self.elev = d["elev"]
        self.noise = d.get("noise_m", 2.0)
        self.obtained_at = d.get("obtained_at")
        self.edges = d["edges"]
        self.adj = [[] for _ in self.lat]
        for k, (u, v, *_rest) in enumerate(self.edges):
            self.adj[u].append((v, k, True))
            self.adj[v].append((u, k, False))
        self.beach = set(d.get("beach", []))
        self.grid = {}
        for i in range(len(self.lat)):
            if self.adj[i]:
                self.grid.setdefault(self._cell(self.lat[i], self.lon[i]), []).append(i)

    def _xy(self, lat, lon):
        return lon * M_LON, lat * M_LAT

    def _cell(self, lat, lon):
        x, y = self._xy(lat, lon)
        return int(x // CELL), int(y // CELL)

    def dist(self, a, b):
        ax, ay = self._xy(self.lat[a], self.lon[a])
        bx, by = self._xy(self.lat[b], self.lon[b])
        return math.hypot(ax - bx, ay - by)

    def nearest(self, lat, lon):
        """Ближайший узел дороги к точке (вход отеля, магазин) — или None, если дорог рядом нет."""
        cx, cy = self._cell(lat, lon)
        x, y = self._xy(lat, lon)
        best = None
        for r in range(0, SNAP_MAX // CELL + 2):
            for i in range(cx - r, cx + r + 1):
                for j in range(cy - r, cy + r + 1):
                    if max(abs(i - cx), abs(j - cy)) != r:
                        continue
                    for k in self.grid.get((i, j), ()):
                        d = math.hypot(*(a - b for a, b in zip(self._xy(self.lat[k], self.lon[k]), (x, y))))
                        if best is None or d < best[0]:
                            best = (d, k)
            if best and best[0] <= r * CELL:
                break
        return best[1] if best and best[0] <= SNAP_MAX else None

    def _cost(self, k, fwd):
        e = self.edges[k]
        t = e[3] if fwd else e[4]
        return t * (1.15 if e[7] & MAJOR and not e[7] & FOOT else 1.0)   # вдоль трассы идти не хочется

    def astar(self, s, t):
        if s == t:
            return [], 0.0
        g = {s: 0.0}
        prev = {}
        pq = [(self.dist(s, t) / V_MAX, s)]
        while pq:
            _, u = heapq.heappop(pq)
            if u == t:
                break
            gu = g[u]
            for v, k, fwd in self.adj[u]:
                nv = gu + self._cost(k, fwd)
                if nv < g.get(v, math.inf):
                    g[v] = nv
                    prev[v] = (u, k, fwd)
                    heapq.heappush(pq, (nv + self.dist(v, t) / V_MAX, v))
        if t not in prev:
            return None, None
        return self._path(prev, s, t), g[t]

    def dijkstra(self, s, cutoff_s=None, targets=None):
        """Время до всех узлов в пределах cutoff_s; с targets — остановиться на ближайшей цели."""
        g = {s: 0.0}
        prev = {}
        pq = [(0.0, s)]
        done = set()
        while pq:
            gu, u = heapq.heappop(pq)
            if u in done:
                continue
            done.add(u)
            if targets is not None and u in targets:
                return g, prev, u
            for v, k, fwd in self.adj[u]:
                nv = gu + self._cost(k, fwd)
                if (cutoff_s is None or nv <= cutoff_s) and nv < g.get(v, math.inf):
                    g[v] = nv
                    prev[v] = (u, k, fwd)
                    heapq.heappush(pq, (nv, v))
        return g, prev, None

    def _path(self, prev, s, t):
        steps = []
        v = t
        while v != s:
            u, k, fwd = prev[v]
            steps.append((k, fwd))
            v = u
        return steps[::-1]

    def describe(self, s, path, start_pt=None, end_pt=None):
        """Маршрут как линия + честные цифры: метры, минуты туда/обратно, подъём, лестницы, переходы."""
        coords = [[self.lon[s], self.lat[s]]]
        meters = t_f = t_b = 0.0
        node_elev = [self.elev[s]]
        flags = {"steps": 0, "underpass": 0, "bridge": 0, "rail": 0, "major_m": 0.0}
        for k, fwd in path:
            u, v, length, tf, tb, _up, _down, f, geom = self.edges[k]
            pts = [[geom[i + 1] / 1e5, geom[i] / 1e5] for i in range(0, len(geom), 2)]
            end = v if fwd else u
            coords += (pts if fwd else pts[::-1]) + [[self.lon[end], self.lat[end]]]
            node_elev.append(self.elev[end])
            meters += length
            t_f += tf if fwd else tb
            t_b += tb if fwd else tf
            flags["steps"] += bool(f & STEPS)
            flags["underpass"] += bool(f & TUNNEL)
            flags["bridge"] += bool(f & BRIDGE)
            flags["rail"] += bool(f & RAIL)
            if f & MAJOR and not f & FOOT:
                flags["major_m"] += length
        up, down = self._climb(node_elev)
        # от точки отеля до ближайшей дороги и от дороги до места — прямой отрезок, чтобы линия
        # начиналась в отеле, а не на соседней улице; время на него — обычным шагом
        for pt, at_start in ((start_pt, True), (end_pt, False)):
            if pt:
                d = math.hypot((pt[1] - coords[0 if at_start else -1][0]) * M_LON,
                               (pt[0] - coords[0 if at_start else -1][1]) * M_LAT)
                coords.insert(0, [pt[1], pt[0]]) if at_start else coords.append([pt[1], pt[0]])
                meters += d
                t_f += d / SNAP_SPEED
                t_b += d / SNAP_SPEED
        return {"coords": coords, "meters": round(meters), "minutes": max(1, round(t_f / 60)),
                "back_minutes": max(1, round(t_b / 60)), "up_m": round(up), "down_m": round(down),
                "flags": {**flags, "major_m": round(flags["major_m"])}}

    def _climb(self, zs):
        """Набор и сброс высоты с порогом шума: колебания меньше noise_m не считаем."""
        up = down = 0.0
        ref = zs[0]
        for z in zs[1:]:
            if z - ref >= self.noise:
                up += z - ref
                ref = z
            elif ref - z >= self.noise:
                down += ref - z
                ref = z
        return up, down


@lru_cache(maxsize=1)
def graph():
    path = SEED / "walk_graph.json.gz"
    if not path.exists():
        return None
    import json
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return Graph(json.load(f))


def route(a_lat, a_lon, b_lat, b_lon):
    """Маршрут между двумя точками или None (нет графа / точка далеко от дорог / не связаны)."""
    g = graph()
    if g is None:
        return None
    s, t = g.nearest(a_lat, a_lon), g.nearest(b_lat, b_lon)
    if s is None or t is None:
        return None
    path, _ = g.astar(s, t)
    if path is None:
        return None
    return g.describe(s, path, start_pt=(a_lat, a_lon), end_pt=(b_lat, b_lon))


def to_beach(lat, lon, cutoff_min=40):
    """Путь до ближайшего по времени выхода к пляжу/берегу или None."""
    g = graph()
    if g is None or not g.beach:
        return None
    s = g.nearest(lat, lon)
    if s is None:
        return None
    _, prev, hit = g.dijkstra(s, cutoff_s=cutoff_min * 60, targets=g.beach)
    if hit is None:
        return None
    return g.describe(s, g._path(prev, s, hit) if hit != s else [], start_pt=(lat, lon))
