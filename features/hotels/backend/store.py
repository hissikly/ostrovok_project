from functools import lru_cache

from core.seed import load


@lru_cache(maxsize=1)
def _by_id():
    return {h["id"]: h for h in load("hotels.json") or []}


def hotels() -> list[dict]:
    return list(_by_id().values())


def hotel(hotel_id: str) -> dict | None:
    return _by_id().get(hotel_id)
