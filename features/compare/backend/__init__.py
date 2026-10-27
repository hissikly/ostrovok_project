"""Сравнение отелей и «было / стало». Публичный интерфейс: compare(ids, lens_ids, ctx), baseline(lens_ids, ctx), ordinary(lens_ids)."""
from features.compare.backend.baseline import baseline, ordinary  # noqa: F401
from features.compare.backend.compare import compare  # noqa: F401
