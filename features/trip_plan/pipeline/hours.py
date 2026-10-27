"""Часы работы мест для планировщика дня: музей открыт в 15:00? бар работает в 22:00?

В data/seed/poi.json часов нет (только флаг «круглосуточно»), а планировщику важно не вести
гостя в закрытый музей. Берём opening_hours из той же выгрузки OSM для типов мест,
которые встают в день по интересам.

Вход:  data/raw/osm_poi.json (features/data_sources/pipeline/queries/poi.overpassql)
Выход: data/seed/trip_hours.json — {"obtained_at", "hours": {"node/123": "Mo-Su 10:00-20:00"}}

Запуск: .venv/bin/python features/trip_plan/pipeline/hours.py
"""
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data" / "raw" / "osm_poi.json"
OUT = ROOT / "data" / "seed" / "trip_hours.json"
KEYS = {
    "amenity": {"bar", "pub", "nightclub", "cafe", "restaurant", "fast_food", "theatre", "cinema", "bicycle_rental", "place_of_worship"},
    "tourism": {"museum", "gallery", "attraction", "zoo", "aquarium", "theme_park"},
    "leisure": {"water_park", "swimming_pool", "fitness_centre", "sports_centre", "park", "garden"},
}


def main():
    if not SRC.exists():
        print(f"нет {SRC.relative_to(ROOT)} — пропускаем, планировщик живёт без часов")
        return
    raw = json.load(open(SRC, encoding="utf-8"))
    hours = {}
    for e in raw["elements"]:
        t = e.get("tags") or {}
        oh = t.get("opening_hours")
        if oh and any(t.get(k) in v for k, v in KEYS.items()):
            hours[f"{e['type']}/{e['id']}"] = oh.strip()
    obtained = dt.datetime.fromtimestamp(SRC.stat().st_mtime).date().isoformat()
    OUT.write_text(json.dumps({"obtained_at": obtained, "hours": hours}, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    print(f"часы работы: {len(hours)} мест → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
