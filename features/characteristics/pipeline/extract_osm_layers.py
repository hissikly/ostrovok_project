"""Слои OSM для агента-исследователя: «всё, что есть на карте» вокруг отелей Сочи.

Фильтры «что рядом» (features/nearby) берут только свои 36 типов мест. Агенту, который
добавляет характеристику по описанию («есть ли рядом велодорожки», «нет ли рядом стройки»),
нужен запас: любые теги amenity/shop/leisure/tourism/sport/…, линии (велодорожки, реки, канатные
дороги) и границы площадей (промзоны, кладбища, стройки). Линии и границы сохраняем точками
через каждые ~50 м — расстояние до ближайшей точки и есть «сколько идти до велодорожки».

    .venv/bin/python features/characteristics/pipeline/extract_osm_layers.py

Вход:  data/raw/osm/south-fed-district.osm.pbf (как для пешеходного графа, см. data_sources)
Выход: data/seed/osm_layers.json.gz —
       {"obtained_at", "source", "layers": {"ключ=значение": [[lat, lon, название, "way/123"], …]}}
       data/seed/hotel_tags.json — теги OSM самих отелей (wifi, доступная среда, курение…)
"""
import datetime as dt
import gzip
import json
import math
from collections import defaultdict
from pathlib import Path

import osmium

ROOT = Path(__file__).resolve().parents[3]
PBF = ROOT / "data/raw/osm/south-fed-district.osm.pbf"
OUT = ROOT / "data/seed/osm_layers.json.gz"
HOTEL_TAGS = ROOT / "data/seed/hotel_tags.json"
PAD = 0.02                       # ~2 км вокруг крайних отелей
STEP_M = 50                      # шаг точек вдоль линий
MIN_COUNT = 2                    # совсем редкие теги (опечатки) не берём

# какие ключи OSM берём целиком (значение — любое)
KEYS = ("amenity", "shop", "leisure", "tourism", "sport", "historic", "craft", "office", "healthcare",
        "aerialway", "religion", "waterway", "man_made", "cycleway", "club")
# у этих ключей — только перечисленные значения (остальное — шум или его слишком много)
SOME = {
    "highway": {"cycleway", "pedestrian", "bus_stop", "steps"},
    "natural": {"beach", "wood", "water", "cliff", "peak", "spring", "cave_entrance", "waterfall", "scrub"},
    "landuse": {"construction", "industrial", "cemetery", "forest", "military", "railway", "landfill",
                "garages", "vineyard", "orchard", "allotments", "recreation_ground"},
    "building": {"construction"},
    "bicycle": {"designated"},
    "railway": {"station", "halt", "tram_stop", "rail"},
    "power": {"line", "substation", "plant"},
}
SKIP = {"amenity=bench", "amenity=waste_basket", "amenity=parking_space", "amenity=vending_machine",
        "man_made=pipeline", "man_made=survey_point", "man_made=street_cabinet", "amenity=recycling",
        "amenity=waste_disposal", "man_made=utility_pole", "leisure=picnic_table"}
# теги отеля, которые что-то говорят гостю (остальное — адреса, контакты, названия)
HOTEL_KEYS = ("internet_access", "internet_access:fee", "wheelchair", "smoking", "air_conditioning", "rooms", "beds",
              "swimming_pool", "pets", "dog", "breakfast", "reservation", "toilets:wheelchair", "check_date",
              "payment:cash", "payment:visa", "payment:mastercard", "payment:mir", "payment:credit_cards",
              "opening_hours", "start_date", "operator", "brand", "stars")

LAT0 = 43.58
M_LAT, M_LON = 110_540, 111_320 * math.cos(math.radians(LAT0))


def bbox():
    hs = json.load(open(ROOT / "data/seed/hotels.json"))
    return (min(h["lat"] for h in hs) - PAD, min(h["lon"] for h in hs) - PAD,
            max(h["lat"] for h in hs) + PAD, max(h["lon"] for h in hs) + PAD)


def kinds(tags) -> list[str]:
    out = []
    for k, v in tags.items():
        if k in KEYS or v in SOME.get(k, ()):
            for one in v.split(";"):
                kv = f"{k}={one.strip()}"
                if one.strip() and kv not in SKIP and (k in KEYS or one.strip() in SOME[k]):
                    out.append(kv)
    return out


def sample(locs) -> list[tuple[float, float]]:
    """Точки вдоль линии не реже чем через STEP_M."""
    out = [locs[0]]
    for (a_lat, a_lon), (b_lat, b_lon) in zip(locs, locs[1:]):
        d = math.hypot((b_lat - a_lat) * M_LAT, (b_lon - a_lon) * M_LON)
        n = max(1, int(d // STEP_M))
        out += [(a_lat + (b_lat - a_lat) * i / n, a_lon + (b_lon - a_lon) * i / n) for i in range(1, n + 1)]
    return out


def main():
    s, w, n, e = bbox()
    box = osmium.osm.Box(osmium.osm.Location(w, s), osmium.osm.Location(e, n))
    layers = defaultdict(list)
    objects = defaultdict(int)
    fp = osmium.FileProcessor(str(PBF)).with_locations().with_filter(osmium.filter.KeyFilter(*KEYS, *SOME))
    for obj in fp:
        tags = dict(obj.tags)
        ks = kinds(tags)
        if not ks or obj.is_relation():
            continue
        name = tags.get("name", "")
        if obj.is_node():
            if not box.contains(obj.location):
                continue
            pts, oid = [(obj.location.lat, obj.location.lon)], f"node/{obj.id}"
        else:
            locs = [(nd.location.lat, nd.location.lon) for nd in obj.nodes if nd.location.valid()]
            if not locs or not any(s <= la <= n and w <= lo <= e for la, lo in locs):
                continue
            pts, oid = sample(locs), f"way/{obj.id}"
        for kv in ks:
            objects[kv] += 1
            layers[kv] += [[round(la, 5), round(lo, 5), name, oid] for la, lo in pts if s <= la <= n and w <= lo <= e]
    layers = {kv: pts for kv, pts in layers.items() if objects[kv] >= MIN_COUNT and pts}
    stamp = dt.date.fromtimestamp(PBF.stat().st_mtime).isoformat()
    with gzip.open(OUT, "wt", encoding="utf-8") as f:
        json.dump({"obtained_at": stamp, "source": f"OpenStreetMap, выгрузка Geofabrik от {stamp}",
                   "objects": {kv: objects[kv] for kv in layers}, "layers": layers}, f,
                  ensure_ascii=False, separators=(",", ":"))
    pts = sum(len(v) for v in layers.values())
    print(f"{OUT.relative_to(ROOT)}: {len(layers)} тегов, {pts} точек, {OUT.stat().st_size // 1024} КБ")
    hotel_tags()


def hotel_tags():
    """Теги OSM самих отелей: что отель сам о себе отметил на карте."""
    hs = {h["osm"]: h["id"] for h in json.load(open(ROOT / "data/seed/hotels.json"))}
    out = {}
    for el in json.load(open(ROOT / "data/raw/osm_hotels.json"))["elements"]:
        hid = hs.get(f"{el['type']}/{el['id']}")
        tags = {k: v for k, v in el.get("tags", {}).items() if k in HOTEL_KEYS}
        if hid and tags:
            out[hid] = tags
    json.dump(out, open(HOTEL_TAGS, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"{HOTEL_TAGS.relative_to(ROOT)}: теги у {len(out)} отелей")


if __name__ == "__main__":
    main()
