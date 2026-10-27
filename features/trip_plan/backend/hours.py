"""Открыто ли место в нужное время — по opening_hours OSM (data/seed/trip_hours.json, pipeline/hours.py).

Разбираем частые записи: «24/7», «Mo-Su 10:00-20:00», «Mo-Fr 12:00-22:30; Sa 12:00-23:00»,
«08:00-22:00», «Mo off», время через полночь («17:00-02:00»). Что не разобрали — None:
«не знаем», а не «закрыто».
"""
import re
from functools import lru_cache

from core.seed import load

DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
RANGE = re.compile(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})")


@lru_cache(maxsize=1)
def _hours():
    d = load("trip_hours.json") or {}
    return d.get("hours", {})


def _days(spec):
    """«Mo-Fr,Su» → {0..4, 6}; пусто — все дни; None — не разобрали."""
    if not spec:
        return set(range(7))
    out = set()
    for part in spec.split(","):
        a, _, b = part.strip().partition("-")
        if a not in DAYS or (b and b not in DAYS):
            return None
        i, j = DAYS.index(a), DAYS.index(b or a)
        out |= set(range(i, j + 1)) if i <= j else set(range(i, 7)) | set(range(0, j + 1))
    return out


def _parse(oh):
    """[(дни, [(с, до) в минутах])] по порядку правил; None — не разобрали."""
    rules = []
    for rule in oh.split(";"):
        rule = rule.strip()
        if not rule:
            continue
        m = re.match(r"^((?:[A-Z][a-z](?:-[A-Z][a-z])?,?)+)\s+(.*)$", rule)
        days, rest = (m.group(1), m.group(2)) if m else ("", rule)
        ds = _days(days)
        if ds is None:
            return None
        if rest in ("off", "closed"):
            rules.append((ds, []))
            continue
        spans = [(int(a) * 60 + int(b), int(c) * 60 + int(d)) for a, b, c, d in RANGE.findall(rest)]
        if not spans:
            return None
        rules.append((ds, spans))
    return rules or None


def opening(osm_id):
    """Часы работы как в OSM или None."""
    return _hours().get(osm_id)


def is_open(osm_id, weekday, start, minutes):
    """Открыто ли всё время с start (минуты от полуночи) на minutes минут: True / False / None (часов нет)."""
    oh = opening(osm_id)
    if not oh:
        return None
    if oh.strip() == "24/7":
        return True
    if oh.strip() in ("closed", "off"):
        return False
    rules = _parse(oh)
    if rules is None:
        return None
    spans = None
    for ds, sp in rules:   # позднее правило для того же дня главнее
        if weekday in ds:
            spans = sp
    if spans is None:
        return False
    end = start + minutes
    for a, b in spans:
        if b <= a:          # через полночь: 17:00-02:00
            b += 24 * 60
        if a <= start and end <= b:
            return True
    return False


def closes(osm_id, weekday):
    """«до 20:00» для подписи или None."""
    rules = _parse(opening(osm_id) or "") if opening(osm_id) and opening(osm_id) != "24/7" else None
    if not rules:
        return "круглосуточно" if opening(osm_id) == "24/7" else None
    spans = None
    for ds, sp in rules:
        if weekday in ds:
            spans = sp
    if not spans:
        return None
    b = spans[-1][1] % (24 * 60)
    return f"до {b // 60:02d}:{b % 60:02d}"
