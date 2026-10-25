"""Пешеходный граф Сочи для маршрутов: OSM-дороги + высоты из карты высот, время по Тоблеру.

Вход:  data/raw/walk/*.json (features/data_sources/pipeline/fetch_walk.py),
       data/raw/Copernicus_*.tif, data/raw/osm_coast.json (пляжи и берег)
Выход: data/seed/walk_graph.json.gz — компактный граф, по нему core/walk.py строит маршруты.

Как устроено:
- Узлы графа — только перекрёстки, концы улиц и ж/д переезды; промежуточные точки улицы
  хранятся геометрией ребра (рисовать маршрут), так граф в разы меньше.
- Высота узла — из Copernicus GLO-30. Это модель поверхности (с крышами и кронами), поэтому берём
  минимум по окну 3×3 пикселя (~90 м) — ближе к земле. Перепады меньше 2 м не считаем подъёмом (шум).
- Время ребра в обе стороны — функция Тоблера: 6·exp(−3,5·|уклон+0,05|) км/ч, лестницы ×1,2.
- Флаги ребра: лестница, подземный/надземный переход, крупная дорога, ж/д переезд, пешеходная дорожка.

python features/beach_route/pipeline/build_walk_graph.py
"""
import datetime as dt
import gzip
import json
import math
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[3]
RAW, SEED = ROOT / "data/raw", ROOT / "data/seed"
DEM_TILES = {39: RAW / "Copernicus_DSM_COG_10_N43_00_E039_00_DEM.tif",
             40: RAW / "Copernicus_DSM_COG_10_N43_00_E040_00_DEM.tif"}
TO_M = Transformer.from_crs("EPSG:4326", "EPSG:32637", always_xy=True)
STEPS, TUNNEL, BRIDGE, MAJOR, RAIL, FOOT = 1, 2, 4, 8, 16, 32
MAJOR_HW = {"primary", "primary_link", "trunk", "trunk_link", "secondary", "secondary_link"}
FOOT_HW = {"footway", "path", "pedestrian", "steps", "living_street", "corridor"}
NOISE_M = 2.0
BEACH_NEAR_M = 30


class Dem:
    """Высота «ближе к земле»: минимум по окну 3×3 из Copernicus DSM."""

    def __init__(self):
        self.tiles = {}
        for lon0, path in DEM_TILES.items():
            with rasterio.open(path) as ds:
                a = ds.read(1).astype(np.float32)
                tr = ds.transform
            p = np.pad(a, 1, mode="edge")
            m = a.copy()
            for di in (0, 1, 2):
                for dj in (0, 1, 2):
                    np.minimum(m, p[di:di + a.shape[0], dj:dj + a.shape[1]], out=m)
            self.tiles[lon0] = (m, ~tr)

    def __call__(self, lat, lon):
        m, inv = self.tiles[int(math.floor(lon))]
        c, r = inv * (lon, lat)
        r, c = min(max(int(r), 0), m.shape[0] - 1), min(max(int(c), 0), m.shape[1] - 1)
        return max(0.0, float(m[r, c]))


def tobler_s(d, dh, steps):
    """Секунды на отрезок длиной d м с перепадом dh м."""
    if d < 0.5:
        return 0.0
    s = max(-0.6, min(0.6, dh / d))
    v = 6 * math.exp(-3.5 * abs(s + 0.05)) / 3.6
    return d / v * (1.2 if steps else 1.0)


def load_osm():
    ways, rail_nodes = {}, set()
    for path in sorted((RAW / "walk").glob("*.json")):
        for el in json.load(open(path))["elements"]:
            if el["type"] == "way" and el.get("geometry") and len(el["nodes"]) >= 2:
                ways[el["id"]] = el
            elif el["type"] == "node":
                rail_nodes.add(el["id"])
    return ways, rail_nodes


def way_flags(tags):
    f = 0
    hw = tags.get("highway", "")
    if hw == "steps":
        f |= STEPS
    if tags.get("tunnel") in ("yes", "building_passage") or tags.get("layer", "0").startswith("-"):
        f |= TUNNEL
    if tags.get("bridge") == "yes":
        f |= BRIDGE
    if hw in MAJOR_HW:
        f |= MAJOR
    if hw in FOOT_HW:
        f |= FOOT
    return f


def beach_shapes():
    out = []
    for el in json.load(open(RAW / "osm_coast.json"))["elements"]:
        kind = el.get("tags", {}).get("natural")
        g = [TO_M.transform(p["lon"], p["lat"]) for p in el.get("geometry") or []]
        if el["type"] == "way" and kind == "coastline" and len(g) >= 2:
            out.append(LineString(g))
        elif el["type"] == "way" and kind == "beach" and len(g) >= 4:
            out.append(Polygon(g).buffer(0))
        elif el["type"] == "relation" and kind == "beach":
            for m in el.get("members", []):
                mg = [TO_M.transform(p["lon"], p["lat"]) for p in m.get("geometry") or []]
                if m.get("role") == "outer" and len(mg) >= 4:
                    out.append(Polygon(mg).buffer(0))
    return out


def main():
    ways, rail_nodes = load_osm()
    dem = Dem()
    # какие узлы OSM станут узлами графа: концы улиц, общие для нескольких улиц, переезды
    use = {}
    for w in ways.values():
        for nid in w["nodes"]:
            use[nid] = use.get(nid, 0) + 1
    keep = {nid for nid, k in use.items() if k > 1} | rail_nodes
    for w in ways.values():
        keep.add(w["nodes"][0])
        keep.add(w["nodes"][-1])

    idx, coords, elev = {}, [], {}

    def node(nid, lat, lon):
        if nid not in idx:
            idx[nid] = len(coords)
            coords.append((lat, lon))
        return idx[nid]

    def h(nid, lat, lon):
        if nid not in elev:
            elev[nid] = dem(lat, lon)
        return elev[nid]

    edges = []
    for w in ways.values():
        tags = w.get("tags", {})
        flags = way_flags(tags)
        pts = list(zip(w["nodes"], w["geometry"]))
        start = 0
        for i in range(1, len(pts)):
            nid = pts[i][0]
            if nid not in keep and i < len(pts) - 1:
                continue
            seg = pts[start:i + 1]
            length = t_f = t_b = 0.0
            geom = []
            prev = None
            for k, (sid, g) in enumerate(seg):
                x, y = TO_M.transform(g["lon"], g["lat"])
                z = h(sid, g["lat"], g["lon"])
                if prev:
                    d = math.hypot(x - prev[0], y - prev[1])
                    dz = z - prev[2]
                    length += d
                    t_f += tobler_s(d, dz, flags & STEPS)
                    t_b += tobler_s(d, -dz, flags & STEPS)
                if 0 < k < len(seg) - 1:
                    geom += [round(g["lat"] * 1e5), round(g["lon"] * 1e5)]
                prev = (x, y, z)
            # подъём/спуск ребра — по высотам концов (шум внутри ребра не копим)
            z0 = h(seg[0][0], seg[0][1]["lat"], seg[0][1]["lon"])
            z1 = h(seg[-1][0], seg[-1][1]["lat"], seg[-1][1]["lon"])
            up, down = max(0.0, z1 - z0), max(0.0, z0 - z1)
            u = node(seg[0][0], seg[0][1]["lat"], seg[0][1]["lon"])
            v = node(seg[-1][0], seg[-1][1]["lat"], seg[-1][1]["lon"])
            f = flags | (RAIL if seg[0][0] in rail_nodes or seg[-1][0] in rail_nodes else 0)
            if u != v and length > 0:
                edges.append([u, v, round(length, 1), round(t_f, 1), round(t_b, 1),
                              round(up, 1), round(down, 1), f, geom])
            start = i
    # узлы у пляжа/берега — цели маршрута «до пляжа»
    shapes = beach_shapes()
    tree = STRtree(shapes)
    beach = []
    for i, (lat, lon) in enumerate(coords):
        x, y = TO_M.transform(lon, lat)
        p = Point(x, y)
        near = tree.query(p.buffer(BEACH_NEAR_M))
        if any(shapes[j].distance(p) <= BEACH_NEAR_M for j in near):
            beach.append(i)
    elev_nodes = [0.0] * len(coords)
    for nid, i in idx.items():
        elev_nodes[i] = round(elev.get(nid, 0.0), 1)
    src_date = dt.date.fromtimestamp(min(p.stat().st_mtime for p in (RAW / "walk").glob("*.json"))).isoformat()
    out = {"obtained_at": src_date, "noise_m": NOISE_M,
           "nodes": [v for lat, lon in coords for v in (round(lat * 1e5), round(lon * 1e5))],
           "elev": elev_nodes, "edges": edges, "beach": beach}
    path = SEED / "walk_graph.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"{path.relative_to(ROOT)}: {len(coords)} узлов, {len(edges)} рёбер, у пляжа {len(beach)}, "
          f"{path.stat().st_size / 1e6:.1f} МБ")


if __name__ == "__main__":
    main()
