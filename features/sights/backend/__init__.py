"""Что посмотреть в городе: подборка мест (features/sights/sights.json) и «жить рядом» с ними.

Каждое место — факт sight:<id> у каждого отеля: сколько идти пешком по графу (pipeline/sight_times.py)
или, если пешком больше часа или место вне графа, — честная оценка «на машине» по прямой.
Из фактов собираются фильтры sight_<id> для подбора (features/search) и блок в карточке отеля.
"""
import datetime as dt
import json
import math
from functools import lru_cache
from pathlib import Path

from core.config import SEED
from features.facts.backend import register_provider
from features.hotels.backend import hotels

SIGHTS = Path(__file__).resolve().parents[1] / "sights.json"
WALK_MATCH, WALK_PARTIAL, WALK_MAX = 15, 30, 40   # минут пешком: «рядом» / «можно дойти» / дальше — на машине
CAR_DETOUR, CAR_KMH, CAR_PARK = 1.3, 40, 5   # оценка на машине: прямая ×1,3, 40 км/ч, +5 мин на парковку
LAT0 = 43.58
M_LAT, M_LON = 110_540, 111_320 * math.cos(math.radians(LAT0))


@lru_cache(maxsize=1)
def sights() -> list[dict]:
    items = json.load(open(SIGHTS, encoding="utf-8"))
    credits = _load(SEED / "sights" / "photos.json")
    walk = _walk()
    for s in items:
        s["credit"] = credits.get(s["id"])
        s["walkable"] = any(v[0] <= WALK_PARTIAL * 60 for v in walk.get(s["id"], {}).values())
    return items


def _load(path):
    return json.load(open(path, encoding="utf-8")) if path.exists() else {}


@lru_cache(maxsize=1)
def _walk():
    return _load(SEED / "sights_walk.json")


def by_id(sid):
    return next((s for s in sights() if s["id"] == sid), None)


def _car_min(h, s):
    d = math.hypot((h["lon"] - s["lon"]) * M_LON, (h["lat"] - s["lat"]) * M_LAT)
    return round(d * CAR_DETOUR / 1000 / CAR_KMH * 60 + CAR_PARK), round(d)


def reach(h, s) -> dict:
    """Как добраться от отеля до места: пешком по графу, если до 40 мин, иначе оценка на машине."""
    w = _walk().get(s["id"], {}).get(h["id"])
    if w and w[0] <= WALK_MAX * 60:
        return {"mode": "walk", "minutes": max(1, round(w[0] / 60)), "meters": w[1]}
    minutes, meters = _car_min(h, s)
    return {"mode": "car", "minutes": minutes, "meters": meters}


@lru_cache(maxsize=1)
def _car_best():
    """Ближайший из наших отелей на машине — от него считаем «рядом» для мест, куда пешком не дойти."""
    return {s["id"]: min(_car_min(h, s)[0] for h in hotels()) for s in sights()}


def state(s, r) -> str:
    if r["mode"] == "walk":
        return "match" if r["minutes"] <= WALK_MATCH else "partial" if r["minutes"] <= WALK_PARTIAL else "no"
    if s["walkable"]:
        return "no"
    best = _car_best()[s["id"]]
    return "match" if r["minutes"] <= best + 10 else "partial" if r["minutes"] <= best + 25 else "no"


def text(s, r) -> str:
    if r["mode"] == "walk":
        return f"До {s['to']} {r['minutes']} мин пешком"
    return f"До {s['to']} ≈ {r['minutes']} мин на машине"


def _facts():
    today = dt.date.today()
    out = []
    for h in hotels():
        for s in sights():
            r = reach(h, s)
            walk = r["mode"] == "walk"
            out.append({
                "id": f"{h['id']}:sight:{s['id']}:hotel", "hotel_id": h["id"], "scope": "hotel",
                "characteristic": f"sight:{s['id']}", "value": {**r, "name": s["name"]},
                "confidence": 0.8 if walk else 0.5,
                "source": "computed:osm-walk" if walk else "computed:straight-line",
                "method_version": "sights@0.1",
                "evidence": {"sight": s["id"], "osm": s["osm"],
                             "method": "пешеходный граф OSM, время по Тоблеру" if walk
                             else f"по прямой ×{CAR_DETOUR}, {CAR_KMH} км/ч + {CAR_PARK} мин"},
                "obtained_at": today.isoformat(),
                "valid_until": (today + dt.timedelta(days=365)).isoformat(), "status": "active",
            })
    return out


def nearest(h, limit=3) -> list[dict]:
    """Ближайшие места подборки к отелю — для блока «Что посмотреть рядом» в карточке."""
    rows = [{"id": s["id"], "name": s["name"], "to": s["to"], "lat": s["lat"], "lon": s["lon"], "tags": s["tags"], **reach(h, s)}
            for s in sights()]
    rows.sort(key=lambda r: (r["mode"] != "walk", r["minutes"]))
    return rows[:limit]


register_provider(_facts)
