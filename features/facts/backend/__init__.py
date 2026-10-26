"""Хранилище фактов. Публичный интерфейс для других фич: facts_for(hotel_id), all_facts(), register_provider(fn), refresh()."""
from features.facts.backend.store import all_facts, facts_for, refresh, register_provider  # noqa: F401
