"""Хранилище фактов. Публичный интерфейс для других фич: facts_for(hotel_id), all_facts()."""
from features.facts.backend.store import all_facts, facts_for  # noqa: F401
