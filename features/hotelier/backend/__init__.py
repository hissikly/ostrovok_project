"""Отельер. Публичный интерфейс: ask_hotel(hotel_id, topic, guest_text) — вопрос в очередь (с подсчётом спроса),
open_questions(hotel_id) — что ждёт ответа."""
from features.hotelier.backend.questions import ask_hotel, open_questions  # noqa: F401
