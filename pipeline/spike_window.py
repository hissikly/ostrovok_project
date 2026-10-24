"""Спайк: вид из окна для одного реального отеля Сочи.

python pipeline/spike_window.py --list            # кандидаты
python pipeline/spike_window.py --osm way/123     # расчёт + data/derived/spike_<id>.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from astral import Observer
from astral.sun import azimuth, elevation, sunset
from shapely.geometry import Polygon

from horizon import (EYE_ABOVE_FLOOR, FLOOR_H, LOCAL_RADIUS, Building, Dem, LocalFrame,
                     build_local, building_height, cast, facades, group_facades)

ROOT = Path(__file__).resolve().parent.parent
RAW, OUT = ROOT / "data/raw", ROOT / "data/derived"
DEM_TILES = [RAW / "Copernicus_DSM_COG_10_N43_00_E039_00_DEM.tif",
             RAW / "Copernicus_DSM_COG_10_N43_00_E040_00_DEM.tif"]
TZ = ZoneInfo("Europe/Moscow")


def load_osm(name):
    return json.load(open(RAW / f"osm_{name}.json"))["elements"]


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
    if el["type"] == "node":
        return el["lat"], el["lon"]
    if (b := el.get("bounds")):
        return (b["minlat"] + b["maxlat"]) / 2, (b["minlon"] + b["maxlon"]) / 2
    pts = poly_of(el)
    return float(np.mean([p[0] for p in pts])), float(np.mean([p[1] for p in pts]))


def list_candidates(dem: Dem):
    hotels = load_osm("hotels")
    rows = []
    for h in hotels:
        t = h.get("tags", {})
        if t.get("tourism") != "hotel" or not poly_of(h):
            continue
        lat, lon = centroid(h)
        z = float(dem.sample(lat, lon))
        rows.append((z, t.get("name", "?"), t.get("building:levels", "-"), t.get("stars", "-"),
                     f"{h['type']}/{h['id']}", round(lat, 5), round(lon, 5)))
    rows.sort(reverse=True)
    print(f"отелей с контуром здания: {len(rows)}")
    for r in rows[:60]:
        print(f"{r[0]:6.1f} м | {r[1][:45]:45} | эт. {r[2]:>3} | ★{r[3]} | {r[4]} | {r[5]},{r[6]}")


def sun_events(lat, lon, profile_by_az, eye_ground, months=(4, 5, 6, 7, 8, 9, 10)):
    """Когда солнце реально скрывается из этого окна vs. астрономический закат."""
    obs = Observer(latitude=lat, longitude=lon, elevation=0)
    res = []
    for m in months:
        day = dt.date(2026, m, 15)
        ss = sunset(obs, day, tzinfo=TZ)
        hide, hide_az, blocker = None, None, None
        t = ss - dt.timedelta(minutes=180)
        while t <= ss + dt.timedelta(minutes=5):
            az = azimuth(obs, t) % 360
            el = elevation(obs, t)
            p = profile_by_az.get(int(round(az)) % 360)
            if p is None:                        # солнце вне сектора окна
                hide, blocker = t, "вне обзора окна"
                hide_az = az
                break
            if el < p["angle"]:
                hide, hide_az, blocker = t, az, p["kind"]
                break
            t += dt.timedelta(minutes=1)
        res.append({
            "month": m,
            "sunset_astro": ss.strftime("%H:%M"),
            "sunset_az": round(azimuth(obs, ss) % 360, 1),
            "sun_hidden_at": hide.strftime("%H:%M") if hide else None,
            "hidden_by": blocker,
            "minutes_earlier": round((ss - hide).total_seconds() / 60) if hide else None,
            "sets_into_sea": bool(blocker == "sea"),
        })
    return res


def run(osm_ref: str):
    dem = Dem.load([str(p) for p in DEM_TILES], bounds=(39.2, 43.2, 40.6, 44.0))
    hotels = {f"{h['type']}/{h['id']}": h for h in load_osm("hotels")}
    h = hotels[osm_ref]
    tags = h.get("tags", {})
    lat0, lon0 = centroid(h)
    frame = LocalFrame(lat0, lon0)

    # здания вокруг
    blds = []
    for b in load_osm("buildings"):
        g = b.get("geometry")
        if not g or len(g) < 4:
            continue
        x, y = frame.to_xy([p["lat"] for p in g], [p["lon"] for p in g])
        if np.hypot(x.mean(), y.mean()) > LOCAL_RADIUS + 100:
            continue
        poly = Polygon(zip(x, y)).buffer(0)
        if poly.is_empty:
            continue
        hh, src = building_height(b.get("tags", {}))
        c = poly.centroid
        la, lo = frame.to_latlon(c.x, c.y)
        blds.append(Building(b["id"], poly, hh, src, float(dem.sample(la, lo))))
    srcs = {k: sum(b.height_src == k for b in blds) for k in ("height", "levels", "default")}

    # здание отеля: контур из OSM, ищем совпадающий building
    hp = poly_of(h)
    hx, hy = frame.to_xy([p[0] for p in hp], [p[1] for p in hp])
    hpoly = Polygon(zip(hx, hy)).buffer(0)
    own = max((b for b in blds if b.poly_xy.intersects(hpoly)),
              key=lambda b: b.poly_xy.intersection(hpoly).area, default=None)
    if own is not None and own.poly_xy.area > hpoly.area * 0.3:
        hpoly, own_id, lv_src = own.poly_xy, own.osm_id, own.height_src
    else:
        own_id, lv_src = None, "hotel-tag"
    levels = int(float(tags.get("building:levels") or (own and own.height_src == "levels"
                                                       and round((own.height - 1) / 3)) or 5))
    local = build_local(blds, exclude_id=own_id)
    ground = float(dem.sample(lat0, lon0))

    sides = group_facades(facades(hpoly))
    result = {"hotel": {"osm": osm_ref, "name": tags.get("name"), "lat": lat0, "lon": lon0,
                        "ground_m": round(ground, 1), "levels": levels, "levels_src": lv_src,
                        "stars": tags.get("stars"), "website": tags.get("website")},
              "buildings_nearby": {"count": len(blds), **srcs},
              "facades": {}}
    for side, f in sides.items():
        sector = [int((f.normal_az + d) % 360) for d in range(-80, 81)]
        floors = {}
        for fl in sorted({1, 2, 3, max(1, levels // 2), levels}):
            eye = ground + FLOOR_H * (fl - 1) + EYE_ABOVE_FLOOR
            rays = cast(frame, dem, local, f.x, f.y, eye, sector)
            sea_rays = [r for r in rays if r.sea_visible]
            prof = {r.az: {"angle": round(r.angle, 2), "kind": r.kind, "dist": round(r.dist),
                           "building": r.building, "sea": r.sea_visible} for r in rays}
            elat, elon = frame.to_latlon(f.x, f.y)
            floors[fl] = {
                "eye_m": round(eye, 1),
                "sea_share": round(len(sea_rays) / len(rays), 3),
                "sea_degrees": len(sea_rays),
                "blocked_by_buildings": sum(r.kind == "building" for r in rays),
                "sun": sun_events(float(elat), float(elon), prof, eye),
                "profile": prof,
            }
        elat, elon = frame.to_latlon(f.x, f.y)
        result["facades"][side] = {"normal_az": round(f.normal_az, 1), "eye_lat": float(elat),
                                   "eye_lon": float(elon), "length_m": round(f.length, 1),
                                   "floors": floors}
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"spike_{osm_ref.replace('/', '_')}.json"
    json.dump(result, open(out, "w"), ensure_ascii=False, indent=1)

    print(f"{tags.get('name')} | земля {ground:.0f} м | этажей {levels} ({lv_src}) | "
          f"зданий рядом {len(blds)}: {srcs}")
    for side, fd in result["facades"].items():
        print(f"  фасад {side} (окна на {fd['normal_az']}°):")
        for fl, v in fd["floors"].items():
            may = next(s for s in v["sun"] if s["month"] == 5)
            print(f"    {fl:>2} эт. глаз {v['eye_m']:5.1f} м | море {v['sea_share']*100:4.0f}% "
                  f"({v['sea_degrees']}°) | дома закрыли {v['blocked_by_buildings']}° | "
                  f"май: закат {may['sunset_astro']}, скрылось {may['sun_hidden_at']} "
                  f"({may['hidden_by']}, −{may['minutes_earlier']} мин)")
    print("→", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--osm")
    a = ap.parse_args()
    if a.list:
        list_candidates(Dem.load([str(p) for p in DEM_TILES], bounds=(39.2, 43.2, 40.6, 44.0)))
    else:
        run(a.osm)
