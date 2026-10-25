"""Время пешком по графу от каждого отеля до всех мест «рядом» (до 30 мин).

Вход:  data/seed/hotels.json, data/seed/poi.json (export_poi.py), data/seed/walk_graph.json.gz
Выход: data/seed/poi_walk.json.gz — {hotel_id: [индекс места в poi.json, секунды, …]}

Считаем для всех мест сразу, а не по фильтрам: новый фильтр на уже выгруженных тегах
получает честное время пешком без пересчёта.

python features/nearby/pipeline/walk_times.py
"""
import gzip
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from core.walk import graph  # noqa: E402
from features.hotels.backend import hotels as all_hotels  # noqa: E402  — точка отеля как на карте

CUTOFF_S = 30 * 60
SNAP_SPEED = 1.2   # м/с — от точки места до ближайшей дороги


def main():
    g = graph()
    items = json.load(open(ROOT / "data/seed/poi.json"))["items"]
    by_node = {}
    for i, it in enumerate(items):
        n = g.nearest(it[0], it[1])
        if n is not None:
            extra = math.hypot((it[1] - g.lon[n]) * 80_900, (it[0] - g.lat[n]) * 110_540) / SNAP_SPEED
            by_node.setdefault(n, []).append((i, extra))
    out, n_pairs = {}, 0
    hotels = all_hotels()
    for k, h in enumerate(hotels, 1):
        s = g.nearest(h["lat"], h["lon"])
        if s is None:
            continue
        # от точки отеля до ближайшей дороги — так же, как рисует маршрут core/walk.py
        start = math.hypot((h["lon"] - g.lon[s]) * 80_900, (h["lat"] - g.lat[s]) * 110_540) / SNAP_SPEED
        dist, _, _ = g.dijkstra(s, cutoff_s=CUTOFF_S)
        row = []
        for node, t in dist.items():
            for i, extra in by_node.get(node, ()):
                if start + t + extra <= CUTOFF_S:
                    row += [i, round(start + t + extra)]
        out[h["id"]] = row
        n_pairs += len(row) // 2
        if k % 100 == 0:
            print(f"  {k}/{len(hotels)}")
    path = ROOT / "data/seed/poi_walk.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"{path.relative_to(ROOT)}: {len(out)} отелей, {n_pairs} пар, {path.stat().st_size / 1e6:.1f} МБ")


if __name__ == "__main__":
    main()
