"""Скачивает пешеходную сеть OSM (улицы, тротуары, тропы, лестницы) и ж/д переезды — тайлами.

Весь район отелей одним запросом Overpass не отдаёт. Тайлы ~3×3 км, только те, где есть отели,
+1 км вокруг. Готовые тайлы не перекачиваем.

    .venv/bin/python features/data_sources/pipeline/fetch_walk.py
→ data/raw/walk/<tile>.json (не в git; граф собирает features/beach_route/pipeline/build_walk_graph.py)
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from overpass import query  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data/raw/walk"
TILE_LAT, TILE_LON = 0.027, 0.037        # ≈ 3 × 3 км
PAD_LAT, PAD_LON = 0.009, 0.0125        # ≈ 1 км
WALKABLE = ("footway|path|pedestrian|steps|living_street|residential|service|unclassified|track|"
            "tertiary|tertiary_link|secondary|secondary_link|primary|primary_link|trunk|trunk_link|"
            "cycleway|corridor|bridleway|road")

Q = """[out:json][timeout:180];
(
  way["highway"~"^({hw})$"]["foot"!="no"]["access"!="no"]({b});
  node["railway"~"^(level_crossing|crossing)$"]({b});
);
out body geom qt;
"""


def tile_of(lat, lon):
    return math.floor(lat / TILE_LAT), math.floor(lon / TILE_LON)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    hotels = json.load(open(ROOT / "data/seed/hotels.json"))
    tiles = sorted({tile_of(h["lat"], h["lon"]) for h in hotels})
    print(f"тайлов: {len(tiles)}")
    for n, (ti, tj) in enumerate(tiles, 1):
        out = OUT / f"{ti}_{tj}.json"
        if out.exists():
            continue
        s, w = ti * TILE_LAT - PAD_LAT, tj * TILE_LON - PAD_LON
        nn, e = (ti + 1) * TILE_LAT + PAD_LAT, (tj + 1) * TILE_LON + PAD_LON
        data = query(Q.format(hw=WALKABLE, b=f"{s:.4f},{w:.4f},{nn:.4f},{e:.4f}"))
        json.dump(data, open(out, "w"), ensure_ascii=False)
        print(f"  {n}/{len(tiles)} {out.name}: {len(data.get('elements', []))} элементов")


if __name__ == "__main__":
    main()
