"""Профиль гостя. Публичный интерфейс: profile() — поездки с вопросами «Так и было?» и отзывами, stats() — метрика по фильтрам.

При старте подкладывает две прошлые демо-поездки (одна с ответами и отзывом, другая ждёт ответов)."""
import logging

from features.profile.backend.service import profile, seed_demo, stats  # noqa: F401

try:
    seed_demo()
except Exception:   # демо не должно ронять сервис
    logging.getLogger(__name__).exception("profile: демо-поездки не созданы")
