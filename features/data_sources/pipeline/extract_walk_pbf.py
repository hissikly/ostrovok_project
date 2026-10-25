"""Пешеходная сеть Сочи из готовой выгрузки OSM (Geofabrik) — надёжнее, чем Overpass тайлами.

    curl -L -o data/raw/osm/south-fed-district.osm.pbf \\
         https://download.geofabrik.de/russia/south-fed-district-latest.osm.pbf     # ~320 МБ
    .venv/bin/python features/data_sources/pipeline/extract_walk_pbf.py

→ data/raw/walk/pbf_sochi.json в том же виде, что отдаёт Overpass (`out body geom`):
  ways с nodes/geometry/tags + узлы ж/д переездов. Граф собирает
  features/beach_route/pipeline/build_walk_graph.py — ему всё равно, откуда файлы.
"""
import datetime as dt
import json
import re
import sys
from pathlib import Path

import osmium

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_walk import WALKABLE  # noqa: E402  — тот же список дорог, что и для Overpass

ROOT = Path(__file__).resolve().parents[3]
PBF = ROOT / "data/raw/osm/south-fed-district.osm.pbf"
OUT = ROOT / "data/raw/walk/pbf_sochi.json"
PAD = 0.012                        # ~1 км вокруг крайних отелей
HW = re.compile(f"^({WALKABLE})$")


def bbox():
    hs = json.load(open(ROOT / "data/seed/hotels.json"))
    return (min(h["lat"] for h in hs) - PAD, min(h["lon"] for h in hs) - PAD,
            max(h["lat"] for h in hs) + PAD, max(h["lon"] for h in hs) + PAD)


def main():
    s, w, n, e = bbox()
    box = osmium.osm.Box(osmium.osm.Location(w, s), osmium.osm.Location(e, n))
    elements = []
    fp = (osmium.FileProcessor(str(PBF))
          .with_locations()
          .with_filter(osmium.filter.KeyFilter("highway", "railway")))
    for obj in fp:
        if obj.is_node():
            if obj.tags.get("railway") in ("level_crossing", "crossing") and box.contains(obj.location):
                elements.append({"type": "node", "id": obj.id, "lat": obj.location.lat, "lon": obj.location.lon})
        elif obj.is_way():
            tags = dict(obj.tags)
            if not HW.match(tags.get("highway", "")) or tags.get("foot") == "no" or tags.get("access") == "no":
                continue
            pts = [(nd.ref, nd.location) for nd in obj.nodes if nd.location.valid()]
            if len(pts) < 2 or not any(box.contains(loc) for _, loc in pts):
                continue
            elements.append({"type": "way", "id": obj.id, "nodes": [r for r, _ in pts], "tags": tags,
                             "geometry": [{"lat": loc.lat, "lon": loc.lon} for _, loc in pts]})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    stamp = dt.date.fromtimestamp(PBF.stat().st_mtime).isoformat()
    json.dump({"source": f"geofabrik south-fed-district {stamp}", "elements": elements}, open(OUT, "w"),
              ensure_ascii=False)
    ways = sum(el["type"] == "way" for el in elements)
    print(f"{OUT.relative_to(ROOT)}: {ways} дорог, {len(elements) - ways} ж/д переездов, bbox {s:.3f},{w:.3f},{n:.3f},{e:.3f}")


if __name__ == "__main__":
    main()
