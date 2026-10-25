"""Факты из демо-данных (data/seed/facts_*.json). Модель — wiki/architecture.md.

Пока хранилище в памяти: читаем все facts_*.json при старте. SQLite появится,
когда факты начнут писаться онлайн (ответы отельера, «так и было?»).
"""
from collections import defaultdict
from functools import lru_cache

from core.config import SEED
from core.seed import load


@lru_cache(maxsize=1)
def _index():
    by_hotel = defaultdict(list)
    n = 0
    for path in sorted(SEED.glob("facts_*.json")):
        for f in load(path.name) or []:
            n += 1
            f = {"id": f"{f['hotel_id']}:{f['characteristic']}:{f['scope']}", **f}
            by_hotel[f["hotel_id"]].append(f)
    return by_hotel, n


def facts_for(hotel_id: str) -> list[dict]:
    return _index()[0].get(hotel_id, [])


def all_facts() -> dict[str, list[dict]]:
    return _index()[0]
