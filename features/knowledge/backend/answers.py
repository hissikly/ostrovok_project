"""Ответ на вопрос гостя: понять тему → найти ответ → честно сказать «не знаем».

Где ищем, по убыванию доверия:
1. ответ отеля (база знаний, уровень отеля); если он расходится с расчётом — показываем обе версии
   («мнения расходятся», features/conflicts), пока отель не поправит ответ или не объяснит его;
2. то, что система посчитала сама (факты: этажность, вид из окна, путь до пляжа, что рядом);
2½. что отель пишет на своём сайте — с дословной цитатой и ссылкой (features/web_sources);
3. общее знание выше: город → край → страна (налог, вода в море, тип пляжей).
Ничего не нашли → status "unknown": интерфейс предлагает спросить у отеля. Ответ не придумываем.
"""
import json
from functools import lru_cache
from pathlib import Path

from core.textmatch import best, meaning_key
from features.conflicts.backend import check as check_conflict, site_conflict
from features.facts.backend import facts_for
from features.hotels.backend import hotel
from features.nearby.backend import specs as nearby_specs
from features.web_sources.backend import answer as web_answer, ask as web_ask, topics_for as web_topics

from .store import get, hotel_path, lookup

TOPICS = Path(__file__).resolve().parents[1] / "topics.json"
SIDE = {"N": "север", "E": "восток", "S": "юг", "W": "запад"}
MONTH_IN = ["", "январе", "феврале", "марте", "апреле", "мае", "июне", "июле", "августе", "сентябре",
            "октябре", "ноябре", "декабре"]
LEVEL_NOTE = {"hotel": "Так ответил отель", "computed": "Посчитали сами", "web": "С сайта отеля", "city": "Общее для Сочи",
              "region": "Общее для Краснодарского края", "country": "Общее для России"}


@lru_cache(maxsize=1)
def topics() -> list[dict]:
    return json.load(open(TOPICS, encoding="utf-8"))


def topic(tid: str) -> dict | None:
    return next((t for t in topics() if t["id"] == tid), None)


def _fact(facts, char):
    return [f for f in facts if f["characteristic"] == char and f["status"] == "active"]


# --- ответы из посчитанных фактов -------------------------------------------------------------

def _floors(h, facts, ctx):
    if h and h.get("levels"):
        return {"text": f"В корпусе {h['levels']} этажей", "value": {"floors": h["levels"]},
                "source": "osm", "confidence": 0.7}


def _sea_view(h, facts, ctx):
    fs = _fact(facts, "sea_view")
    if not fs:
        return None
    parts = []
    for f in sorted(fs, key=lambda f: "WSNE".index(f["scope"][-1])):
        v, side = f["value"], SIDE[f["scope"][-1]]
        if v["from_floor"]:
            floor = "с любого этажа" if v["from_floor"] == 1 else f"с {v['from_floor']}-го"
            parts.append(f"на {side} — {floor}")
        elif v["glimpse_from"]:
            parts.append(f"на {side} — краешком с {v['glimpse_from']}-го")
    text = ("Море видно из окон " + ", ".join(parts)) if parts else "Моря из окон не видно"
    return {"text": text, "value": {"sides": {f["scope"][-1]: f["value"]["from_floor"] for f in fs}},
            "source": fs[0]["source"], "confidence": min(f["confidence"] for f in fs)}


def _beach(h, facts, ctx):
    r = _fact(facts, "beach_route")
    if r:
        v = r[0]["value"]
        back = f", обратно {v['back_minutes']} мин" + (f" в гору на {v['climb_back_m']} м" if v.get("climb_back_m", 0) >= 10 else "")
        return {"text": f"До пляжа {v['minutes']} мин пешком{back}", "value": v,
                "source": r[0]["source"], "confidence": r[0]["confidence"]}
    d = _fact(facts, "beach_distance")
    if d:
        v = d[0]["value"]
        return {"text": f"До пляжа около {v['walk_min']} мин пешком", "value": v,
                "source": d[0]["source"], "confidence": d[0]["confidence"]}


COMPUTED = {"floors": _floors, "sea_view": _sea_view, "beach": _beach}


def _swim_text(k, ctx):
    """Знание города «вода по месяцам» → ответ под месяц поездки."""
    m = ctx.get("month")
    t = k["value"]["sea_c"].get(str(m)) if m else None
    if t is None:
        return k["text"]
    t = round(t)
    feel = "тёплое" if t >= 22 else "можно купаться" if t >= 20 else "бодрит, купаются немногие" if t >= 17 else "холодное"
    return f"В {MONTH_IN[m]} море около {t}°: {feel}"


# --- поиск ответа --------------------------------------------------------------------------

def resolve(hotel_id: str, tid: str, ctx: dict) -> dict:
    t = topic(tid)
    path = hotel_path(hotel_id)
    base = {"topic": tid, "question": t["question"], "icon": t["icon"], "can_ask_hotel": bool(t.get("ask_hotel"))}
    own = get(path, tid)                       # 1. ответ отеля
    if own:
        demo = " (демо)" if (own.get("evidence") or {}).get("demo") else ""
        out = {**base, "status": "answered", "level": "hotel", "note": LEVEL_NOTE["hotel"] + demo, "text": own["text"],
               "value": own["value"], "source": own["source"], "confidence": own["confidence"],
               "obtained_at": own["obtained_at"]}
        # ответ отеля сверяем с расчётом: расходятся — гость видит обе версии, пока отель не объяснит
        comp = COMPUTED[tid](hotel(hotel_id), facts_for(hotel_id), ctx) if tid in COMPUTED else None
        c = check_conflict(tid, own, comp)
        if c:
            explained = (own.get("evidence") or {}).get("explanation")
            out["conflict"] = {**c, "status": "explained" if explained else "open", "explanation": explained}
            if not explained:
                out["note"] = "Мнения расходятся — уточняем у отеля" + demo
                out["confidence"] = min(own["confidence"], comp.get("confidence") or 1)
        return out
    if tid in COMPUTED:                        # 2. посчитали сами
        h = hotel(hotel_id)
        a = COMPUTED[tid](h, facts_for(hotel_id), ctx)
        if a:
            out = {**base, "status": "answered", "level": "computed", "note": LEVEL_NOTE["computed"], **a}
            c = site_conflict(hotel_id, tid, a)     # на своём сайте отель обещает иное — гость видит обе версии
            if c:
                out.update(conflict=c, note="Отель пишет иначе — уточняем", confidence=min(a["confidence"], 0.6))
            return out
    w = web_answer(hotel_id, tid)              # 2½. с сайта отеля
    if w:
        return {**base, "status": "answered", "level": "web", "note": LEVEL_NOTE["web"], **w}
    k = lookup(path, tid)                      # 3. общее знание выше
    if k:
        text = _swim_text(k, ctx) if tid == "swim" else k["text"]
        return {**base, "status": "answered", "level": k["level"], "note": LEVEL_NOTE[k["level"]], "text": text,
                "value": k["value"], "source": k["source"], "confidence": k["confidence"],
                "obtained_at": k["obtained_at"]}
    return {**base, "status": "unknown", "text": "Этого мы пока не знаем :("}


def _near(hotel_id: str, sid: str) -> dict | None:
    s = next((x for x in nearby_specs() if x["id"] == sid), None)
    f = next((f for f in facts_for(hotel_id) if f["characteristic"] == f"near:{sid}"), None)
    if not s or not f:
        return None
    v = f["value"]
    if v["meters"] is None:
        text = f"{s['kind']}: на карте в {v['within_min']} мин пешком не нашли"
    else:
        name = f"{v['kind']} «{v['name']}»" if v.get("name") else v["kind"]
        text = f"{name} в {v['walk_min']} мин пешком"
    return {"topic": f"near:{sid}", "question": s["title"], "icon": s["icon"], "status": "answered",
            "level": "computed", "note": LEVEL_NOTE["computed"], "text": text, "value": v,
            "source": f["source"], "confidence": f["confidence"], "can_ask_hotel": False}


def ask(hotel_id: str, text: str, ctx: dict) -> dict:
    """Вопрос гостя об отеле своими словами → ответы по найденным темам или «не знаем»."""
    found = [tid for tid, _ in best(text, topics())]
    site = web_ask(hotel_id, text, quotes=False) if not found else None   # «есть ли бассейн» — тема сайта отеля
    near = [sid for sid, _ in best(text, nearby_specs())] if not found and not site else []
    answers = [resolve(hotel_id, tid, ctx) for tid in found] + [a for a in (_near(hotel_id, s) for s in near) if a]
    answers += [site] if site else []
    if not answers:
        # вопрос не из каталога, но отель на него уже отвечал (по смыслу фразы)
        note = get(hotel_path(hotel_id), "note:" + meaning_key(text))
        if note:
            return {"status": "answered", "can_ask_hotel": False, "answers": [{
                "topic": "note", "question": text.strip(), "icon": "question", "status": "answered", "level": "hotel",
                "note": LEVEL_NOTE["hotel"], "text": note["text"], "value": note["value"], "source": "hotelier",
                "confidence": note["confidence"], "obtained_at": note["obtained_at"], "can_ask_hotel": False}]}
        w = web_ask(hotel_id, text)            # нет в каталоге — ищем на сайте отеля, ответ с цитатой
        if w:
            return {"status": "answered", "can_ask_hotel": False, "answers": [w]}
        return {"status": "no_topic", "text": "Этого мы пока не знаем :(", "question": text.strip(),
                "can_ask_hotel": True, "answers": []}
    unknown = all(a["status"] == "unknown" for a in answers)
    return {"status": "unknown" if unknown else "answered", "answers": answers,
            "can_ask_hotel": any(a["status"] == "unknown" and a["can_ask_hotel"] for a in answers)}


FAQ = ["sea_view", "beach", "swim", "floors", "checkin", "pets", "parking", "breakfast", "tourist_tax", "beach_type"]


def faq(hotel_id: str, ctx: dict) -> list[dict]:
    """Частые вопросы для карточки отеля: сначала то, на что есть ответ."""
    extra = [t for t in dict.fromkeys(web_topics(hotel_id)) if t not in FAQ and topic(t)]  # ещё ответы с сайта
    items = [resolve(hotel_id, tid, ctx) for tid in FAQ + extra]
    return sorted(items, key=lambda a: a["status"] != "answered")
