"""Источники шума Сочи из выгрузки OSM (Geofabrik): крупные дороги, железная дорога,
взлётная полоса аэропорта, бары и ночные клубы.

    .venv/bin/python features/noise/pipeline/extract_sources.py
→ data/raw/noise_sources.json (не в git; шум по сторонам здания считает noise.py)

Выгрузка: data/raw/osm/south-fed-district.osm.pbf (см. features/data_sources/pipeline/extract_walk_pbf.py).
"""
import json
from pathlib import Path

import osmium

ROOT = Path(__file__).resolve().parents[3]
PBF = ROOT / "data/raw/osm/south-fed-district.osm.pbf"
OUT = ROOT / "data/raw/noise_sources.json"
PAD = 0.02   # ~2 км вокруг крайних отелей: шум трассы слышно и из-за угла района
ROADS = {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
         "secondary", "secondary_link", "tertiary", "tertiary_link"}
NIGHT = {"bar", "pub", "nightclub"}


def bbox():
    hs = json.load(open(ROOT / "data/seed/hotels.json"))
    return (min(h["lat"] for h in hs) - PAD, min(h["lon"] for h in hs) - PAD,
            max(h["lat"] for h in hs) + PAD, max(h["lon"] for h in hs) + PAD)


def main():
    s, w, n, e = bbox()
    box = osmium.osm.Box(osmium.osm.Location(w, s), osmium.osm.Location(e, n))
    lines, points = [], []
    fp = (osmium.FileProcessor(str(PBF))
          .with_locations()
          .with_filter(osmium.filter.KeyFilter("highway", "railway", "aeroway", "amenity")))
    for obj in fp:
        tags = obj.tags
        if obj.is_node():
            if tags.get("amenity") in NIGHT and box.contains(obj.location):
                points.append({"kind": tags["amenity"], "name": tags.get("name", ""), "hours": tags.get("opening_hours", ""),
                               "lat": obj.location.lat, "lon": obj.location.lon})
            continue
        if not obj.is_way():
            continue
        pts = [(nd.location.lat, nd.location.lon) for nd in obj.nodes if nd.location.valid()]
        if len(pts) < 2 or not any(box.contains(osmium.osm.Location(lon, lat)) for lat, lon in pts):
            continue
        hw, rw = tags.get("highway"), tags.get("railway")
        if hw in ROADS:
            kind = hw.replace("_link", "")
        elif rw == "rail" and tags.get("service") not in ("yard", "siding", "spur"):
            kind = "rail"
        elif tags.get("aeroway") == "runway":
            kind = "runway"
        elif tags.get("amenity") in NIGHT:   # бар контуром здания — берём центр
            lat = sum(p[0] for p in pts) / len(pts)
            lon = sum(p[1] for p in pts) / len(pts)
            points.append({"kind": tags["amenity"], "name": tags.get("name", ""), "hours": tags.get("opening_hours", ""),
                           "lat": lat, "lon": lon})
            continue
        else:
            continue
        lines.append({"kind": kind, "name": tags.get("name", ""), "tunnel": tags.get("tunnel") == "yes",
                      "pts": [[round(a, 6), round(b, 6)] for a, b in pts]})
    json.dump({"lines": lines, "points": points}, open(OUT, "w"), ensure_ascii=False)
    from collections import Counter
    print(f"{OUT.relative_to(ROOT)}: линий {len(lines)} {dict(Counter(l['kind'] for l in lines))}, "
          f"ночных мест {len(points)} {dict(Counter(p['kind'] for p in points))}")


if __name__ == "__main__":
    main()
