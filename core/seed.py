"""Чтение демо-данных из data/seed (собираются pipeline-скриптами фич и лежат в git)."""
import json
from functools import lru_cache

from core.config import SEED


@lru_cache(maxsize=None)
def load(name: str):
    path = SEED / name
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)
