"""Сайты отелей. Публичный интерфейс: answer(hotel_id, topic), ask(hotel_id, text), topics_for(hotel_id),
search(hotel_id, question, k) — инструмент web_text для агента; summary(hotel_id), stats()."""
from features.web_sources.backend.search import search  # noqa: F401
from features.web_sources.backend.store import answer, ask, stats, summary, topics_for, web_facts  # noqa: F401
