"""«Было / стало»: как отсортировал бы обычный сайт и где эта выдача разочаровала бы гостя.

Обычный поиск знает только карточку: рейтинг, цену и «до моря по прямой». Сортируем по рейтингу,
при равенстве — ближе к морю по прямой. Если гость просит пляж рядом, сайт отфильтровал бы
«до моря до 1 км по прямой» — делаем так же.
Подвох — включённая гостем линза, которая по нашим фактам отвечает «нет» (ночью шумно, обратно
в гору, моря не видно). «Не знаем» подвохом не считаем — показываем отдельно.
"""
from features.facts.backend import all_facts
from features.hotels.backend import hotels
from features.search.backend.ranking import search
from features.search.backend.lenses import BY_ID, MATCH, NO, PARTIAL, UNKNOWN

BEACH_LENSES = ("beach_near", "flat")
SITE_RADIUS_M = 1000
TOP = 10


def _straight(facts) -> int | None:
    f = next((f for f in facts if f["characteristic"] == "beach_distance" and f["status"] == "active"), None)
    return f["value"]["meters"] if f else None


def ordinary(lens_ids: list[str]) -> list[dict]:
    """Порядок «как на сайте»: [{id, line_m}] — рейтинг ↓, до моря по прямой ↑, цена ↑."""
    facts = all_facts()
    rows = [{"h": h, "line_m": _straight(facts.get(h["id"], []))} for h in hotels()]
    if any(l in BEACH_LENSES for l in lens_ids):
        rows = [r for r in rows if r["line_m"] is not None and r["line_m"] <= SITE_RADIUS_M]
    rows.sort(key=lambda r: (-r["h"]["mock"]["rating"], r["line_m"] if r["line_m"] is not None else 1e9,
                             r["h"]["mock"]["price_rub"]))
    return [{"id": r["h"]["id"], "line_m": r["line_m"]} for r in rows]


def baseline(lens_ids: list[str], ctx: dict, top: int = 30) -> dict:
    lens_ids = [l for l in dict.fromkeys(lens_ids) if l in BY_ID]
    ours = search(lens_ids, ctx)
    our_rank = {r["id"]: k for k, r in enumerate(ours["hotels"], 1)}
    reasons = {r["id"]: r["reasons"] for r in ours["hotels"]}
    base = ordinary(lens_ids)
    out = []
    for k, b in enumerate(base[:top], 1):
        rs = reasons.get(b["id"], [])
        out.append({"id": b["id"], "rank": k, "our_rank": our_rank.get(b["id"]), "line_m": b["line_m"],
                    "traps": [r["text"] for r in rs if r["state"] == NO],
                    "unknown": [r["text"] for r in rs if r["state"] == UNKNOWN],
                    "ok": [{"text": r["text"], "state": r["state"]} for r in rs if r["state"] in (MATCH, PARTIAL)]})
    head = out[:TOP]
    return {"lenses": lens_ids, "hotels": out,
            "rank": {b["id"]: k for k, b in enumerate(base, 1)},
            "summary": {"top": len(head), "traps": sum(bool(h["traps"]) for h in head),
                        "unknown": sum(bool(h["unknown"]) and not h["traps"] for h in head),
                        "kinds": _kinds(head)}}


def _kinds(head: list[dict]) -> list[str]:
    """Какие подвохи встретились наверху обычной выдачи — для одной фразы в плашке."""
    seen = []
    for h in head:
        for t in h["traps"]:
            k = ("шумно ночью" if "шумно" in t else "обратно в гору" if "в гору" in t
                 else "пляж далеко" if "До пляжа" in t else "моря не видно" if "Моря" in t
                 else "закат не виден" if "Закат" in t else None)
            if k and k not in seen:
                seen.append(k)
    return seen
