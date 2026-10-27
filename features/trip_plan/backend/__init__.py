"""День по интересам. Публичный интерфейс: plan(...) — сцены и трасса для ленты дня, fit_all(interests) — для списка."""
from features.trip_plan.backend.fit import fit_all  # noqa: F401
from features.trip_plan.backend.interests import INTERESTS  # noqa: F401
from features.trip_plan.backend.plan import plan  # noqa: F401
