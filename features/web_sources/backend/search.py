"""Поиск по текстам сайтов отелей (инструмент web_text): BM25 по леммам, работает без ключа LLM.

Чанки — data/seed/web_chunks.json.gz (pipeline/index.py). Индекс строится лениво на отель:
у отеля десятки–сотни чанков, леммы считаются за доли секунды при первом вопросе.
"""
import gzip
import json
import math
from collections import Counter, defaultdict
from functools import lru_cache

from core.config import SEED
from core.textmatch import STOP, lemmas

K1, B = 1.5, 0.75


@lru_cache(maxsize=1)
def _chunks() -> dict[str, list[dict]]:
    path = SEED / "web_chunks.json.gz"
    by = defaultdict(list)
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for c in json.load(f):
                by[c["hotel_id"]].append(c)
    return by


def chunks_for(hotel_id: str) -> list[dict]:
    return _chunks().get(hotel_id, [])


def terms(text: str) -> list[str]:
    return [w for w in lemmas(text) if w not in STOP and len(w) > 1]


@lru_cache(maxsize=256)
def _index(hotel_id: str):
    docs = [Counter(terms(c["title"] + "\n" + c["text"])) for c in chunks_for(hotel_id)]
    df = Counter(t for d in docs for t in d)
    avg = sum(sum(d.values()) for d in docs) / max(1, len(docs))
    return docs, df, avg


def search(hotel_id: str, question: str, k: int = 4, reviews: bool = False) -> list[dict]:
    """Лучшие чанки сайта отеля под вопрос: [{text, url, title, fetched_at, score, matched}];
    matched — доля слов вопроса, найденных в чанке (для порога «нашли ответ»)."""
    cs = chunks_for(hotel_id)
    if not cs:
        return []
    docs, df, avg = _index(hotel_id)
    q = list(dict.fromkeys(terms(question)))
    n = len(docs)
    out = []
    for c, d in zip(cs, docs):
        if c.get("reviews") and not reviews:
            continue
        L = sum(d.values()) or 1
        s, hit = 0.0, 0
        for t in q:
            tf = d.get(t, 0)
            if not tf:
                continue
            hit += 1
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            s += idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * L / avg))
        if s > 0:
            out.append({**c, "score": round(s, 3), "matched": round(hit / max(1, len(q)), 2)})
    return sorted(out, key=lambda x: -x["score"])[:k]
