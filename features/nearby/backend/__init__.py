"""Что рядом. Публичный интерфейс: specs() — каталог фильтров, compute(spec) — факты по описанию.

При импорте подключает свои факты near:<id> к хранилищу фактов.
"""
from features.facts.backend import register_provider
from features.nearby.backend.tool import all_nearby_facts, compute, specs  # noqa: F401

register_provider(all_nearby_facts)
