"""Компактная выгрузка объектов OSM для фильтров «что рядом».

Вход:  data/raw/osm_poi.json (features/data_sources/pipeline/queries/poi.overpassql)
Выход: data/seed/poi.json — {"obtained_at", "items": [[lat, lon, "ключ=значение", название, круглосуточно, "node/123"]]}

Берём только теги, которые встречаются в каталоге фильтров (features/nearby/specs.json):
сервису не нужно таскать лишнее, а новый фильтр на уже выгруженных тегах считается без перекачки.

python features/nearby/pipeline/export_poi.py
"""
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KEYS = ("shop", "amenity", "leisure", "tourism", "highway", "railway", "healthcare")


def main():
    src = ROOT / "data/raw/osm_poi.json"
    specs = json.load(open(ROOT / "features/nearby/specs.json", encoding="utf-8"))
    wanted = {t for s in specs for t in s["osm"]}
    items = []
    for el in json.load(open(src))["elements"]:
        tags = el.get("tags", {})
        if el["type"] == "node":
            lat, lon = el["lat"], el["lon"]
        elif el.get("center"):
            lat, lon = el["center"]["lat"], el["center"]["lon"]
        else:
            continue
        # бассейны в OSM — в основном частные у домов: берём только открытые для всех
        if tags.get("leisure") == "swimming_pool" and tags.get("access") not in ("yes", "public", "customers"):
            continue
        for k in KEYS:
            kv = f"{k}={tags.get(k)}"
            if k in tags and kv in wanted:
                items.append([round(lat, 6), round(lon, 6), kv, tags.get("name", ""),
                              1 if tags.get("opening_hours", "").strip() == "24/7" else 0, f"{el['type']}/{el['id']}"])
                break
    obtained = dt.date.fromtimestamp(src.stat().st_mtime).isoformat()
    out = ROOT / "data/seed/poi.json"
    json.dump({"obtained_at": obtained, "items": items}, open(out, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"{out.relative_to(ROOT)}: {len(items)} объектов")


if __name__ == "__main__":
    main()
