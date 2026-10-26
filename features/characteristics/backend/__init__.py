"""Характеристики и агент-исследователь. Публичный интерфейс: all_specs(), get_spec(id), places(hotel_id, id),
hotel_view(hotel_id), TOOLS — реестр инструментов.

При импорте: читает добавленные описанием характеристики, отдаёт их факты в хранилище фактов
и линзы в поиск. Встроенные «да / нет» считаются в фоне при старте сервиса (router: startup).
"""
from features.facts.backend import register_provider
from features.characteristics.backend.store import (all_specs, facts, get_spec, hotel_view, load, places,  # noqa: F401
                                                    register_lenses)
from features.characteristics.backend.tools import TOOLS  # noqa: F401

load()
register_provider(facts)
register_lenses()
