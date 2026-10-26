"""Утренний кофе: ближайшее пешком кафе, где правда можно позавтракать или выпить кофе утром.

Не любое amenity=cafe: в OSM так отмечены и шашлычные, и мясные рестораны («Мясной синдикат»).
Берём кафе, если по тегам OSM видно, что оно утреннее:
  - часы работы (opening_hours) — открывается не позже 09:00 или 24/7;
  - кухня (cuisine) — кофейня, завтраки, выпечка, десерты;
  - название — «кофе», «coffee», «завтрак», «пекарня»… (слабее всего).
Если часы есть и открывается позже 09:00 — не берём, даже если это кофейня.

Вход:  data/raw/osm_poi.json (features/data_sources/pipeline/queries/poi.overpassql),
       data/seed/hotels.json, data/seed/walk_graph.json.gz (пешеходный граф)
Выход: data/seed/day_cafes.json —
  {"obtained_at", "hotels": {hotel_id: {name, lat, lon, walk_min, meters, why, opens, confidence, osm}}}

Запуск: .venv/bin/python features/day/pipeline/morning_cafes.py
"""
import datetime as dt
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from core.walk import route  # noqa: E402

SRC = ROOT / "data" / "raw" / "osm_poi.json"
OUT = ROOT / "data" / "seed" / "day_cafes.json"
MORNING = "09:00"   # открыто к этому времени — годится для утреннего кофе
MAX_WALK = 15       # минут; сцена в ленте берёт ≤10, запас — на будущее
NEAREST = 6         # сколько ближайших по прямой проверяем по графу
RADIUS_M = 1200
COFFEE_CUISINE = {"coffee_shop", "breakfast", "cake", "pastry", "bakery", "dessert", "crepe", "pancake", "tea"}
COFFEE_NAME = re.compile(r"кофе|coffee|кофейн|espresso|эспрессо|бариста|barista|завтрак|breakfast|пекарн|bakery|булочн|круассан|croissant",
                         re.I)
M_LAT = 111_320


def opens(oh):
    """Самое раннее открытие по opening_hours («Mo-Su 08:00-21:00; Sa 10:00-…») или None."""
    if not oh:
        return None
    if oh.strip() == "24/7":
        return "00:00"
    starts = re.findall(r"(\d{1,2}:\d{2})\s*-\s*\d{1,2}:\d{2}", oh)
    return min((s.zfill(5) for s in starts), default=None)


def morning(tags):
    """(годится ли для утра, почему, во сколько открывается, уверенность)."""
    op = opens(tags.get("opening_hours"))
    cuisine = set(tags.get("cuisine", "").replace(" ", "").split(";")) & COFFEE_CUISINE
    named = bool(COFFEE_NAME.search(tags.get("name", "")))
    if op and op > MORNING:
        return False, None, op, 0
    if op and cuisine:
        return True, "кофейня, открыта с утра", op, 0.85
    if cuisine:
        return True, "кофейня" if "coffee_shop" in cuisine else "завтраки и выпечка", None, 0.75
    if op:
        return True, "открыто с утра", op, 0.7
    if named:
        return True, "кофейня по названию", None, 0.6
    return False, None, None, 0


def main():
    if not SRC.exists():
        print(f"нет {SRC.relative_to(ROOT)} — пропускаем, остаётся {OUT.name} из git")
        return
    hotels = json.load(open(ROOT / "data" / "seed" / "hotels.json", encoding="utf-8"))
    hotels = hotels if isinstance(hotels, list) else hotels.get("hotels", hotels.get("items", []))
    cafes = []
    for el in json.load(open(SRC, encoding="utf-8"))["elements"]:
        t = el.get("tags", {})
        if t.get("amenity") != "cafe" or not t.get("name"):
            continue
        ok, why, op, conf = morning(t)
        if not ok:
            continue
        lat, lon = (el["lat"], el["lon"]) if "lat" in el else (el["center"]["lat"], el["center"]["lon"])
        cafes.append({"name": t["name"], "lat": lat, "lon": lon, "why": why, "opens": op, "confidence": conf,
                      "osm": f"{el['type']}/{el['id']}"})
    out = {}
    for h in hotels:
        m_lon = M_LAT * math.cos(math.radians(h["lat"]))
        near = sorted(((math.hypot((c["lat"] - h["lat"]) * M_LAT, (c["lon"] - h["lon"]) * m_lon), c) for c in cafes),
                      key=lambda x: x[0])
        best = None
        for d, c in near[:NEAREST]:
            if d > RADIUS_M:
                break
            r = route(h["lat"], h["lon"], c["lat"], c["lon"])
            if r and r["minutes"] <= MAX_WALK and (best is None or r["minutes"] < best["walk_min"]):
                best = {**c, "walk_min": r["minutes"], "meters": r["meters"]}
        if best:
            out[h["id"]] = best
    OUT.write_text(json.dumps({"obtained_at": dt.date.today().isoformat(), "hotels": out}, ensure_ascii=False,
                              separators=(",", ":")), encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: утренних кафе {len(cafes)}, отелей с кофе ≤{MAX_WALK} мин — {len(out)} из {len(hotels)}")


if __name__ == "__main__":
    main()
