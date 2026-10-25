"""Скачивает дома OSM вокруг отелей — по тайлам, а не одним запросом.

Весь Сочи (92 тыс. зданий) Overpass одним куском не отдаёт (504). Режем на тайлы
~2×2 км, берём только тайлы, где есть отели с контуром, каждый расширяем на 1 км
(радиус расчёта вида из окна — 700 м). Готовые тайлы не перекачиваем.

    .venv/bin/python features/data_sources/pipeline/fetch_buildings.py
→ data/raw/buildings/<tile>.json
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from overpass import query  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data/raw"
OUT = RAW / "buildings"
TILE_LAT, TILE_LON = 0.018, 0.025       # ≈ 2 × 2 км
PAD_LAT, PAD_LON = 0.009, 0.0125        # ≈ 1 км


def tile_of(lat, lon):
    return math.floor(lat / TILE_LAT), math.floor(lon / TILE_LON)


def hotel_centers():
    for h in json.load(open(RAW / "osm_hotels.json"))["elements"]:
        if h.get("tags", {}).get("tourism") == "hotel" and h["type"] != "node" and h.get("bounds"):
            b = h["bounds"]
            yield (b["minlat"] + b["maxlat"]) / 2, (b["minlon"] + b["maxlon"]) / 2


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tiles = sorted({tile_of(lat, lon) for lat, lon in hotel_centers()})
    print(f"тайлов с отелями: {len(tiles)}")
    for n, (ti, tj) in enumerate(tiles, 1):
        path = OUT / f"{ti}_{tj}.json"
        if path.exists():
            continue
        s, w = ti * TILE_LAT - PAD_LAT, tj * TILE_LON - PAD_LON
        nn, e = (ti + 1) * TILE_LAT + PAD_LAT, (tj + 1) * TILE_LON + PAD_LON
        q = f'[out:json][timeout:240];way["building"]({s:.5f},{w:.5f},{nn:.5f},{e:.5f});out tags geom qt;'
        data = query(q)
        json.dump(data, open(path, "w"), ensure_ascii=False)
        print(f"  {n}/{len(tiles)} {path.name}: {len(data['elements'])} домов", flush=True)


if __name__ == "__main__":
    main()
