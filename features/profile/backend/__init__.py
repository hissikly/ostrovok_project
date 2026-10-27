"""Профиль гостя. Публичный интерфейс: profile() — поездки с вопросами «Так и было?» и отзывами, stats() — метрика по фильтрам.

При старте подкладывает две прошлые демо-поездки (одна с ответами и отзывом, другая ждёт ответов)
и демо-отзывы о Pullman и Azimut; hotel_reviews(hotel_id) — отзывы для карточки отеля и Экстранета."""
import logging

from features.profile.backend.service import hotel_reviews, profile, seed_demo, seed_demo_reviews, stats  # noqa: F401

try:
    seed_demo()
    seed_demo_reviews()
except Exception:   # демо не должно ронять сервис
    logging.getLogger(__name__).exception("profile: демо-поездки не созданы")
