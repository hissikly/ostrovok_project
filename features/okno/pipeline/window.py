"""Вид из окна для одного отеля: фасады × этажи → профиль горизонта и закат по месяцам.

Метод — wiki/window-view-method.md, проверка на данных — wiki/data-check-sochi.md.
Входы: data/raw/osm_hotels.json, data/raw/buildings/*.json (fetch_buildings.py), тайлы Copernicus.

    .venv/bin/python features/okno/pipeline/window.py way/201474333   # один отель, печать сводки
    .venv/bin/python features/okno/pipeline/compute_all.py             # все отели с контуром
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from astral import Observer
from astral.sun import azimuth, elevation, sunset
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parent))
from horizon import (EYE_ABOVE_FLOOR, FLOOR_H, LOCAL_RADIUS, Building, Dem, LocalFrame,  # noqa: E402
                     build_local, building_height, cast, facades, group_facades)

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data/raw"
TZ = ZoneInfo("Europe/Moscow")
MONTHS = (4, 5, 6, 7, 8, 9, 10)
GROUND_R = 40.0   # м: радиус оценки земли под зданием (одинаковый для отеля и соседей)


# ---------- данные ----------

@lru_cache(maxsize=1)
def dem() -> Dem:
    return Dem.load([str(p) for p in sorted(RAW.glob("Copernicus_*.tif"))], bounds=(39.2, 43.2, 40.6, 44.0))


@lru_cache(maxsize=1)
def hotels() -> dict:
    return {f"{h['type']}/{h['id']}": h for h in json.load(open(RAW / "osm_hotels.json"))["elements"]}


@lru_cache(maxsize=1)
def buildings():
    """Все скачанные дома (без дублей между тайлами) + массивы центров для быстрого отбора."""
    seen, items = set(), []
    for path in sorted((RAW / "buildings").glob("*.json")):
        for b in json.load(open(path))["elements"]:
            g = b.get("geometry")
            if b["id"] in seen or not g or len(g) < 4:
                continue
            seen.add(b["id"])
            items.append((b["id"], b.get("tags", {}), np.array([p["lat"] for p in g]), np.array([p["lon"] for p in g])))
    clat = np.array([it[2].mean() for it in items])
    clon = np.array([it[3].mean() for it in items])
    return items, clat, clon


def poly_of(el):
    g = el.get("geometry")
    if el["type"] == "way" and g and len(g) >= 4:
        return [(p["lat"], p["lon"]) for p in g]
    if el["type"] == "relation":
        outer = [m for m in el.get("members", []) if m.get("role") == "outer" and m.get("geometry")]
        if outer:
            return [(p["lat"], p["lon"]) for p in max(outer, key=lambda m: len(m["geometry"]))["geometry"]]
    return None


def centroid(el):
    b = el.get("bounds")
    if b:
        return (b["minlat"] + b["maxlat"]) / 2, (b["minlon"] + b["maxlon"]) / 2
    return el["lat"], el["lon"]


# ---------- солнце ----------

def sun_events(lat, lon, profile_by_az):
    """Когда солнце реально скрывается из этого окна vs. астрономический закат (15-е число)."""
    obs = Observer(latitude=lat, longitude=lon, elevation=0)
    res = []
    for m in MONTHS:
        ss = sunset(obs, dt.date(2026, m, 15), tzinfo=TZ)
        # идём от заката назад: последняя минута, когда солнце видно из окна
        hide, blocker, t = None, None, ss + dt.timedelta(minutes=6)
        while t >= ss - dt.timedelta(minutes=240):
            p = profile_by_az.get(int(round(azimuth(obs, t) % 360)) % 360)
            if p is not None and elevation(obs, t) > p["angle"]:
                hide = t + dt.timedelta(minutes=1)
                pn = profile_by_az.get(int(round(azimuth(obs, hide) % 360)) % 360)
                blocker = pn["kind"] if pn else "край окна"
                break
            t -= dt.timedelta(minutes=1)
        res.append({
            "month": m,
            "sunset_astro": ss.strftime("%H:%M"),
            "sun_hidden_at": hide.strftime("%H:%M") if hide else None,
            "hidden_by": blocker if hide else "не видно из этого окна",
            "minutes_earlier": max(0, round((ss - hide).total_seconds() / 60)) if hide else None,
            "sets_into_sea": blocker == "sea",
        })
    return res


# ---------- расчёт ----------

def compute(osm_ref: str) -> dict | None:
    h = hotels()[osm_ref]
    tags = h.get("tags", {})
    hp = poly_of(h)
    if not hp:
        return None
    D = dem()
    lat0, lon0 = centroid(h)
    frame = LocalFrame(lat0, lon0)

    # дома в радиусе расчёта
    items, clat, clon = buildings()
    near = np.hypot((clat - lat0) * frame.ky, (clon - lon0) * frame.kx) < LOCAL_RADIUS + 150
    blds = []
    for i in np.flatnonzero(near):
        bid, btags, la, lo = items[i]
        x, y = frame.to_xy(la, lo)
        poly = Polygon(zip(x, y)).buffer(0)
        if poly.is_empty:
            continue
        hh, src = building_height(btags)
        c = poly.centroid
        blds.append(Building(bid, poly, hh, src, D.ground(frame, c.x, c.y, GROUND_R)))
    srcs = {k: sum(b.height_src == k for b in blds) for k in ("height", "levels", "default")}

    # здание отеля; контур в OSM бывает территорией курорта — тогда берём главный корпус внутри
    hx, hy = frame.to_xy([p[0] for p in hp], [p[1] for p in hp])
    hpoly = Polygon(zip(hx, hy)).buffer(0)
    inside = [b for b in blds if b.poly_xy.intersects(hpoly)
              and b.poly_xy.intersection(hpoly).area > 0.5 * b.poly_xy.area]
    own = max(inside, key=lambda b: (b.height_src != "default", b.height * b.poly_xy.area), default=None)
    is_area = "building" not in tags and hpoly.area > 2500
    own_id = None
    if own is not None and (is_area or own.poly_xy.area > hpoly.area * 0.3):
        hpoly, own_id = own.poly_xy, own.osm_id
    try:
        tag_levels = int(float(tags["building:levels"])) if tags.get("building:levels") else None
    except ValueError:
        tag_levels = None
    if tag_levels:
        levels, lv_src = tag_levels, "отель: building:levels"
    elif own is not None and own.height_src in ("levels", "height"):
        levels, lv_src = max(1, round((own.height - 1) / 3)), f"корпус {own.osm_id}: {own.height_src}"
    else:
        levels, lv_src = 5, "нет данных → 5 (спросить отельера)"
    levels = min(levels, 40)

    local = build_local(blds, exclude_id=own_id)
    c = hpoly.centroid
    # тот же радиус, что у соседей: на склоне больший радиус «роняет» отель ниже соседних домов
    ground = D.ground(frame, c.x, c.y, GROUND_R)
    hlat, hlon = (float(v) for v in frame.to_latlon(c.x, c.y))

    result = {"hotel": {"osm": osm_ref, "name": tags.get("name"), "lat": hlat, "lon": hlon,
                        "ground_m": round(ground, 1), "levels": levels, "levels_src": lv_src,
                        "own_building": own_id},
              "buildings_nearby": {"count": len(blds), **srcs},
              "facades": {}}
    floors_to_count = sorted({1, 2, 3, max(1, levels // 2), levels} & set(range(1, levels + 1)))
    for side, f in group_facades(facades(hpoly)).items():
        sector = [int((f.normal_az + d) % 360) for d in range(-80, 81)]
        elat, elon = (float(v) for v in frame.to_latlon(f.x, f.y))
        floors = {}
        for fl in floors_to_count:
            eye = ground + FLOOR_H * (fl - 1) + EYE_ABOVE_FLOOR
            rays = cast(frame, D, local, f.x, f.y, eye, sector, ground)
            prof = {r.az: {"angle": round(r.angle, 2), "kind": r.kind, "dist": round(r.dist), "sea": r.sea_visible}
                    for r in rays}
            floors[fl] = {"eye_m": round(eye, 1),
                          "sea_share": round(sum(r.sea_visible for r in rays) / len(rays), 3),
                          "blocked_by_buildings": sum(r.kind == "building" for r in rays),
                          "sun": sun_events(elat, elon, prof),
                          "profile": prof}
        result["facades"][side] = {"normal_az": round(f.normal_az, 1), "eye_lat": elat, "eye_lon": elon,
                                   "length_m": round(f.length, 1), "floors": floors}
    return result


def summary(r: dict) -> str:
    h = r["hotel"]
    lines = [f"{h['name']} | земля {h['ground_m']:.0f} м | этажей {h['levels']} ({h['levels_src']}) | "
             f"домов рядом {r['buildings_nearby']['count']}"]
    for side, f in r["facades"].items():
        top = f["floors"][max(f["floors"])]
        may = next(s for s in top["sun"] if s["month"] == 5)
        lines.append(f"  {side}: море {', '.join(f'{fl} эт. {v['sea_share']*100:.0f}%' for fl, v in f['floors'].items())}"
                     f" | май, верх: {may['hidden_by']}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(summary(compute(sys.argv[1])))
