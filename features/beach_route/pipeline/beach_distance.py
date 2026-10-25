"""Расстояние от отеля до ближайшего пляжа — по прямой, v0 до настоящего пешего маршрута с рельефом.

Вход:  data/seed/hotels.json, data/raw/osm_coast.json (OSM natural=beach + natural=coastline)
Выход: data/seed/facts_beach.json — факт beach_distance у каждого отеля

python features/beach_route/pipeline/beach_distance.py
"""
import datetime as dt
import json
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[3]
SEED, RAW = ROOT / "data/seed", ROOT / "data/raw"
TO_M = Transformer.from_crs("EPSG:4326", "EPSG:32637", always_xy=True)   # UTM 37N, метры
DETOUR = 1.3        # пеший путь в городе длиннее прямой примерно на треть
WALK_M_MIN = 75     # ~4,5 км/ч


def xy(pts):
    return [TO_M.transform(p["lon"], p["lat"]) for p in pts]


def shapes():
    beaches, coast = [], []
    for el in json.load(open(RAW / "osm_coast.json"))["elements"]:
        kind = el.get("tags", {}).get("natural")
        if el["type"] == "node" and kind == "beach":
            beaches.append(Point(TO_M.transform(el["lon"], el["lat"])))
        elif el["type"] == "way" and el.get("geometry"):
            g = xy(el["geometry"])
            if kind == "coastline" and len(g) >= 2:
                coast.append(LineString(g))
            elif kind == "beach" and len(g) >= 4:
                beaches.append(Polygon(g).buffer(0))
        elif el["type"] == "relation" and kind == "beach":
            for m in el.get("members", []):
                if m.get("role") == "outer" and len(m.get("geometry") or []) >= 4:
                    beaches.append(Polygon(xy(m["geometry"])).buffer(0))
    return beaches, coast


def nearest(tree, geoms, p):
    g = geoms[tree.nearest(p)]
    return g.distance(p)


def main():
    beaches, coast = shapes()
    bt, ct = STRtree(beaches), STRtree(coast)
    today = dt.date.today()
    facts = []
    for h in json.load(open(SEED / "hotels.json")):
        p = Point(TO_M.transform(h["lon"], h["lat"]))
        to_beach, to_coast = nearest(bt, beaches, p), nearest(ct, coast, p)
        # пляж в OSM размечен не везде: если берег заметно ближе размеченного пляжа — считаем до берега
        use_coast = to_coast < to_beach - 150
        d = round(to_coast if use_coast else to_beach)
        facts.append({
            "hotel_id": h["id"], "scope": "hotel", "characteristic": "beach_distance",
            "value": {"meters": d, "walk_min": max(1, round(d * DETOUR / WALK_M_MIN)),
                      "to": "coast" if use_coast else "beach"},
            # по прямой: реальный путь может быть длиннее (ж/д, ограды) — уверенность средняя
            "confidence": 0.55 if use_coast else 0.6,
            "source": "computed:osm-beach", "method_version": "beach-straight@0.1",
            "evidence": {"osm": "natural=coastline" if use_coast else "natural=beach",
                         "method": f"по прямой ×{DETOUR}, {WALK_M_MIN} м/мин"},
            "obtained_at": today.isoformat(),
            "valid_until": (today + dt.timedelta(days=365)).isoformat(), "status": "active",
        })
    out = SEED / "facts_beach.json"
    json.dump(facts, open(out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    near = sum(f["value"]["meters"] <= 500 for f in facts)
    print(f"{out.relative_to(ROOT)}: {len(facts)} отелей, до пляжа ≤500 м — {near}")


if __name__ == "__main__":
    main()
