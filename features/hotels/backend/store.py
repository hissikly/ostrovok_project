from functools import lru_cache

from core.config import SEED
from core.seed import load


def _building_positions() -> dict:
    """Для отелей с посчитанным «О!кном» точка на карте — центр главного корпуса,
    а не центр территории из OSM (у курортов он попадает на пруд или парк)."""
    out = {}
    for path in (SEED / "okno").glob("*.json"):
        d = load(f"okno/{path.name}")
        out[d["hotel_id"]] = (round(d["hotel"]["lat"], 6), round(d["hotel"]["lon"], 6))
    return out


@lru_cache(maxsize=1)
def _by_id():
    pos = _building_positions()
    hotels = {}
    for h in load("hotels.json") or []:
        if h["id"] in pos:
            h = {**h, "lat": pos[h["id"]][0], "lon": pos[h["id"]][1]}
        hotels[h["id"]] = h
    return hotels


@lru_cache(maxsize=1)
def _dups() -> dict:
    """Дубли из OSM (одно здание дважды) → кого оставили; собирает features/hotels/pipeline/dedup.py."""
    return load("hotel_dups.json") or {}


def hotels() -> list[dict]:
    """Отели для выдачи и карты — без дублей. Дубль по прямой ссылке открывается через hotel()."""
    dups = _dups()
    return [h for h in _by_id().values() if h["id"] not in dups]


def hotel(hotel_id: str) -> dict | None:
    return _by_id().get(hotel_id)
