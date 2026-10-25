"""Хранилище фактов. Публичный интерфейс для других фич: facts_for(hotel_id), all_facts(), register_provider(fn)."""
from features.facts.backend.store import all_facts, facts_for, register_provider  # noqa: F401
