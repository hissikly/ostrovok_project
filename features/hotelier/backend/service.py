"""Отельер в Экстранете: вопросы, разбор ответа, подтверждение и правка того, что система узнала сама.

Ответ отеля пишется в базу знаний на уровень отеля (источник hotelier) — гость сразу видит его
в «Частых вопросах» как «Так ответил отель». Если ответ расходится с расчётом, гость видит обе версии,
пока отель не примет расчёт или не объяснит свой ответ (features/conflicts, решение 26.10).
"""
import json
from pathlib import Path

from core.textmatch import meaning_key
from features.facts.backend import facts_for
from features.hotels.backend import hotel
from features.knowledge.backend import hotel_path, resolve, topics, write
from features.knowledge.backend.store import get

from .parse import parse, summary
from .questions import ask_hotel, close, con, demand_total, get_question, open_questions

DEMO = Path(__file__).resolve().parents[1] / "demo_answers.json"
KNOWN = ["sea_view", "beach", "floors"]   # что система узнала сама и просит подтвердить


def _topic(tid):
    return next((t for t in topics() if t["id"] == tid), None)


def parse_answer(topic_id: str | None, text: str) -> dict:
    t = _topic(topic_id) if topic_id else None
    if not t:   # вопрос не из каталога — ответ сохраняем как есть
        return {"fields": [], "summary": text.strip()}
    fields = parse(t, text)
    return {"fields": fields, "summary": summary(fields) or text.strip()}


def save_answer(hotel_id: str, question_id: int | None, topic_id: str | None, text: str,
                fields: list[dict] | None = None, demo: bool = False) -> dict:
    q = get_question(question_id) if question_id else None
    if q:
        topic_id = q["topic"]
    parsed = {"fields": fields, "summary": summary(fields)} if fields is not None else parse_answer(topic_id, text)
    value = {f["id"]: f["value"] for f in parsed["fields"] if f["value"] not in (None, "")}
    key = topic_id or "note:" + meaning_key(q["guest_text"] if q else text)
    k = write(hotel_path(hotel_id), key, value, parsed["summary"] or text.strip(), "hotelier", 0.9,
              evidence={"raw": text, "demo": demo})
    # закрываем все вопросы этого отеля по теме — отель ответил один раз для всех
    for o in open_questions(hotel_id):
        if (topic_id and o["topic"] == topic_id) or (q and o["id"] == q["id"]):
            close(o["id"])
    return k


def agent_questions(hotel_id: str) -> None:
    """Вопросы, которые агент задаёт сам, без гостей: дыры в данных, от которых зависит расчёт."""
    h = hotel(hotel_id)
    has_okno = any(f["characteristic"] == "sea_view" for f in facts_for(hotel_id))
    if h and has_okno and not h.get("levels") and not get(hotel_path(hotel_id), "floors"):
        exists = con().execute("select 1 from questions where hotel_id=? and topic='floors'", (hotel_id,)).fetchone()
        if not exists:
            ask_hotel(hotel_id, "floors", "Вид из окна посчитали для 5 этажей: точной этажности нет на карте", origin="agent")


def cabinet(hotel_id: str, month: int | None = None) -> dict:
    agent_questions(hotel_id)
    qs = []
    for q in open_questions(hotel_id):
        t = _topic(q["topic"]) if q["topic"] else None
        qs.append({**q, "icon": t["icon"] if t else "question",
                   "fields": [{k: f.get(k) for k in ("id", "label", "type", "unit", "options")} for f in t["fields"]] if t else []})
    known = []
    for tid in KNOWN:
        a = resolve(hotel_id, tid, {"month": month})
        if a["status"] == "answered":
            known.append({"topic": tid, "question": a["question"], "icon": a["icon"], "text": a["text"],
                          "by_hotel": a["level"] == "hotel"})
    return {"hotel": {"id": hotel_id, "name": (hotel(hotel_id) or {}).get("name")},
            "demand": demand_total(hotel_id), "questions": qs, "known": known}


def confirm(hotel_id: str, topic_id: str, text: str | None = None) -> dict:
    """«Верно» — отель подтвердил расчёт; «Исправить» — его вариант; расходится с расчётом → features/conflicts."""
    a = resolve(hotel_id, topic_id, {})
    new = (text or "").strip() or a.get("text", "")
    return write(hotel_path(hotel_id), topic_id, {"text": new}, new, "hotelier", 0.95,
                 evidence={"computed": a.get("text"), "action": "corrected" if text else "confirmed"})


def seed_demo() -> int:
    """Имитация отельеров для демо: заранее написанные свободные ответы проходят тот же разбор."""
    n = 0
    for d in json.load(open(DEMO, encoding="utf-8")):
        if hotel(d["hotel_id"]) and not get(hotel_path(d["hotel_id"]), d["topic"]):
            save_answer(d["hotel_id"], None, d["topic"], d["text"], demo=True)
            n += 1
    return n
