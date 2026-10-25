"""Отельер. Публичный интерфейс: ask_hotel(hotel_id, topic, guest_text) — вопрос в очередь (с подсчётом спроса),
open_questions(hotel_id), save_answer(...) — ответ отеля в базу знаний, cabinet(hotel_id) — данные раздела Экстранета.

При старте сервиса подкладывает имитированные ответы отелей для демо (demo_answers.json, пометка demo)."""
from features.hotelier.backend.questions import ask_hotel, open_questions  # noqa: F401
from features.hotelier.backend.service import cabinet, save_answer, seed_demo  # noqa: F401

seed_demo()
