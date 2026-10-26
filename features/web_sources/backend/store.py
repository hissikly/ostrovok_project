"""Что известно с сайта отеля: факты с цитатами (data/seed/facts_web.json) и ответы на вопросы гостя."""
from functools import lru_cache
from urllib.parse import urlparse

from core.seed import load
from core.textmatch import best
from features.facts.backend import facts_for

from ..topics import TOPICS
from .quote import ask_llm, best_sentence
from .search import search

NOTE = "С сайта отеля"
# без ключа отвечаем цитатой, только если кусок явно про вопрос
MIN_MATCHED, MIN_SCORE = 0.75, 2.0


@lru_cache(maxsize=1)
def sites() -> dict[str, dict]:
    data = load("web_sites.json") or {"sites": []}
    return {s["hotel_id"]: s for s in data["sites"]}


def stats() -> dict:
    data = load("web_sites.json") or {"sites": [], "stats": {}}
    facts = load("facts_web.json") or []
    return {"sites": len(data["sites"]), "answered": sum(1 for s in data["sites"] if s["chunks"]),
            "by_status": data["stats"], "facts": len(facts), "hotels_with_facts": len({f["hotel_id"] for f in facts}),
            "topics": sorted({f["evidence"]["topic"] for f in facts})}


def web_facts(hotel_id: str) -> list[dict]:
    return [f for f in facts_for(hotel_id) if f["characteristic"].startswith("web:") and f["status"] == "active"]


def _answer(f: dict) -> dict:
    e = f["evidence"]
    return {"text": f["value"]["text"], "value": {k: v for k, v in f["value"].items() if k != "text"},
            "source": f["source"], "confidence": f["confidence"], "obtained_at": f["obtained_at"],
            "quote": e["quote"], "url": e["url"]}


# тема базы знаний → тема сайта, если называются по-разному («этажи и лифт» ← «есть лифт»)
ALIAS = {"street_noise": "quiet_rooms"}


def answer(hotel_id: str, topic: str) -> dict | None:
    """Ответ на тему базы знаний с сайта отеля: {text, value, source, confidence, obtained_at, quote, url}."""
    topic = ALIAS.get(topic, topic)
    f = next((f for f in web_facts(hotel_id) if f["evidence"]["topic"] == topic), None)
    return _answer(f) if f else None


def topics_for(hotel_id: str) -> list[str]:
    return [f["evidence"]["topic"] for f in web_facts(hotel_id)]


def _topic_meta(tid):
    return next(t for t in TOPICS if t["id"] == tid)


def ask(hotel_id: str, text: str, quotes: bool = True) -> dict | None:
    """Вопрос гостя, которого нет в каталоге базы знаний: сначала темы сайта («есть ли бассейн»),
    потом (quotes) поиск по тексту сайта → ответ с дословной цитатой или None."""
    syn = [t for t in TOPICS if t.get("synonyms")]
    for tid, _ in best(text, syn):
        a = answer(hotel_id, tid)
        if a:
            return {"topic": f"web:{tid}", "question": _topic_meta(tid)["question"], "icon": _topic_meta(tid).get("icon", "question"),
                    "status": "answered", "level": "web", "note": NOTE, "can_ask_hotel": False, **a}
    found = search(hotel_id, text, k=4) if quotes else []
    if not found:
        return None
    r = ask_llm(text, found)
    if r:
        c = r["chunk"]
        return _quote_answer(text, r["answer"] or f"На сайте отеля: «{r['quote']}»", r["quote"], c, 0.6)
    top = found[0]
    if top["matched"] < MIN_MATCHED or top["score"] < MIN_SCORE:
        return None
    s = best_sentence(text, top)
    return _quote_answer(text, f"На сайте отеля: «{s}»", s, top, 0.5) if s else None


def _quote_answer(question, text, quote, c, conf):
    return {"topic": "web", "question": question.strip(), "icon": "question", "status": "answered", "level": "web",
            "note": NOTE, "text": text, "value": None, "source": "web:" + urlparse(c["url"]).netloc.removeprefix("www."),
            "confidence": conf, "obtained_at": c["fetched_at"][:10], "quote": quote, "url": c["url"],
            "can_ask_hotel": False}


def summary(hotel_id: str) -> dict:
    s = sites().get(hotel_id)
    return {"website": s["website"] if s else None, "status": s["status"] if s else None,
            "pages": s["pages"] if s else 0, "fetched_at": s["fetched_at"] if s else None,
            "facts": web_facts(hotel_id)}

