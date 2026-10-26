"""Противоречия источников. Публичный интерфейс: check(topic, hotel_answer, computed),
site_conflict(hotel_id, topic, computed) — сайт отеля ↔ расчёт, TOPICS."""
from features.conflicts.backend.compare import RULES, SITE_TOPIC, check, check_site  # noqa: F401
from features.facts.backend import facts_for
from features.web_sources.backend import answer as _site_answer

TOPICS = list(RULES)


def site_conflict(hotel_id: str, topic: str, computed: dict | None) -> dict | None:
    """Расхождение того, что отель пишет на своём сайте, с расчётом (статус open)."""
    if topic not in SITE_TOPIC:
        return None
    site = _site_answer(hotel_id, SITE_TOPIC[topic])
    if not site:
        return None
    straight = next((f["value"].get("meters") for f in facts_for(hotel_id) if f["characteristic"] == "beach_distance"), None)
    c = check_site(topic, site, computed, straight)
    return {**c, "status": "open", "explanation": None} if c else None
