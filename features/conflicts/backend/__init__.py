"""Противоречия источников. Публичный интерфейс: check(topic, hotel_answer, computed), TOPICS."""
from features.conflicts.backend.compare import RULES, check  # noqa: F401

TOPICS = list(RULES)
