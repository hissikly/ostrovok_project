"""Собирает демо-список отелей Сочи из выгрузки OSM → data/seed/hotels.json.

Запуск (нужны data/raw/osm_hotels.json и тайлы Copernicus, см. features/data_sources):
    .venv/bin/python features/hotels/pipeline/build_hotels.py

Базовые поля карточки (цена, рейтинг, фото) — мок: у Островка нет открытого API,
организаторы разрешили их мокать. Мок помечается полем "mock".
Высота над морем — первый вычисленный факт (DEM), пишется в data/seed/facts_hotels.json.
"""
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "features/okno/pipeline"))
from horizon import Dem, LocalFrame  # noqa: E402

RAW, SEED = ROOT / "data/raw", ROOT / "data/seed"
KINDS = {"hotel": "Отель", "guest_house": "Гостевой дом", "apartment": "Апартаменты",
         "hostel": "Хостел", "motel": "Мотель"}


def hotel_id(el):
    return f"{el['type'][0]}{el['id']}"


def center(el):
    if el["type"] == "node":
        return el["lat"], el["lon"]
    b = el["bounds"]
    return (b["minlat"] + b["maxlat"]) / 2, (b["minlon"] + b["maxlon"]) / 2


def mock_card(hid, stars):
    h = int(hashlib.md5(hid.encode()).hexdigest(), 16)
    base = {None: 4500, 1: 2500, 2: 3200, 3: 4800, 4: 7500, 5: 14000}[stars]
    return {"price_rub": round(base * (0.8 + (h % 50) / 100), -2), "rating": round(7.6 + (h % 23) / 10, 1),
            "reviews": 20 + h % 900}


def main():
    els = json.load(open(RAW / "osm_hotels.json"))["elements"]
    dem = Dem.load([str(p) for p in sorted(RAW.glob("Copernicus_*.tif"))], bounds=(39.2, 43.2, 40.6, 44.0))
    today = dt.date.today().isoformat()
    hotels, facts = [], []
    for el in els:
        t = el.get("tags", {})
        if not t.get("name") or t.get("tourism") not in KINDS:
            continue
        hid = hotel_id(el)
        lat, lon = center(el)
        try:
            stars = int(float(t["stars"])) if t.get("stars") else None
        except ValueError:
            stars = None
        addr = ", ".join(x for x in (t.get("addr:street"), t.get("addr:housenumber")) if x)
        hotels.append({
            "id": hid, "osm": f"{el['type']}/{el['id']}", "name": t["name"],
            "kind": t["tourism"], "kind_ru": KINDS[t["tourism"]],
            "lat": round(lat, 6), "lon": round(lon, 6),
            "stars": stars, "address": addr or None, "levels": t.get("building:levels"),
            "website": t.get("website") or t.get("contact:website"),
            "has_contour": el["type"] != "node",
            "mock": mock_card(hid, stars),
        })
        frame = LocalFrame(lat, lon)
        z = dem.ground(frame, 0.0, 0.0, 40)
        facts.append({
            "hotel_id": hid, "scope": "hotel", "characteristic": "elevation",
            "value": {"meters": round(z)}, "confidence": 0.8,
            "source": "computed:dem", "method_version": "dem-ground@0.1",
            "evidence": {"dem": "Copernicus GLO-30 DSM", "method": "10-й процентиль высот в радиусе 40 м"},
            "obtained_at": today, "valid_until": None, "status": "active",
        })
    hotels.sort(key=lambda h: (h["kind"] != "hotel", h["name"]))
    SEED.mkdir(parents=True, exist_ok=True)
    json.dump(hotels, open(SEED / "hotels.json", "w"), ensure_ascii=False, indent=0)
    json.dump(facts, open(SEED / "facts_hotels.json", "w"), ensure_ascii=False, indent=0)
    print(f"отелей: {len(hotels)} (из них tourism=hotel: {sum(h['kind'] == 'hotel' for h in hotels)}), фактов: {len(facts)}")


if __name__ == "__main__":
    main()
