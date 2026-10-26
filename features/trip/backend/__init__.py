"""«Моя поездка». Публичный интерфейс: wish(...) — пожелание к брони, trip(booking_id, kids) — бронь целиком
(пожелание, обещание, чемодан, ответ отеля), summary(hotel_id) — что подтвердили гости по фактам отеля.

При старте подключает факты-наблюдения гостей к хранилищу фактов и подкладывает демо-ответы «Так и было?»."""
from features.facts.backend import refresh, register_provider
from features.trip.backend.feedback import provider, seed_demo, summary  # noqa: F401
from features.trip.backend.service import trip  # noqa: F401
from features.trip.backend.wish import wish  # noqa: F401

register_provider(provider)
seed_demo()
refresh()
