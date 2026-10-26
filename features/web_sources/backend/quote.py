"""Ответ по тексту сайта с дословной цитатой — с ключом LLM или правилом без него.

Модель отвечает только по найденным кускам сайта; ответ принимаем, только если её цитата
дословно встречается в одном из кусков. Без ключа — лучшее предложение из самого похожего куска,
если в нём есть почти все слова вопроса.
"""
import hashlib
import re
from functools import lru_cache

from core import llm
from core.textmatch import lemmas

PROMPT = """Ты читаешь фрагменты официального сайта отеля. Ответь на вопрос гостя ТОЛЬКО по этим фрагментам.
Вопрос: {question}
{fields}
Верни JSON: {{"found": true|false, {value}"answer": "короткий ответ гостю по-русски, без выдумок", "quote": "дословная цитата из фрагмента, одно предложение"}}
Если во фрагментах нет прямого ответа — {{"found": false}}. Не додумывай. Отзывы гостей — не ответ.

Фрагменты:
{chunks}"""


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("ё", "е").replace("Ё", "Е")).strip().lower().strip(" .;,")


def source_of(quote: str, chunks: list[dict]) -> dict | None:
    """Кусок, в котором цитата есть дословно (с точностью до пробелов и «ё»)."""
    q = norm(quote)
    return next((c for c in chunks if len(q) >= 8 and q in norm(c["text"])), None)


def prompt(question: str, chunks: list[dict], fields: list[dict] | None = None) -> str:
    f = ""
    if fields:
        f = "Поля ответа: " + ", ".join(
            f"{x['id']} ({'/'.join(x['options']) if x.get('options') else x['type']})" for x in fields) + "\n"
    body = "\n\n".join(f"[{i + 1}] {c['text']}" for i, c in enumerate(chunks))
    return PROMPT.format(question=question, fields=f, value='"value": {поля}, ' if fields else "", chunks=body)


def ask_llm(question: str, chunks: list[dict], fields: list[dict] | None = None, cache: dict | None = None) -> dict | None:
    """{value, answer, quote, chunk} или None (нет ключа, нет ответа, цитата не найдена в тексте)."""
    if not chunks or not llm.enabled():
        return None
    p = prompt(question, chunks, fields)
    if cache is not None:
        key = hashlib.sha1((llm.LLM_MODEL + p).encode()).hexdigest()
        if key not in cache:
            cache[key] = llm.chat([{"role": "user", "content": p}], as_json=True)
        r = cache[key]
    else:
        r = _cached(p)
    if not r or not r.get("found") or not r.get("quote"):
        return None
    src = source_of(r["quote"], chunks)
    if not src:
        return None
    value = r.get("value") if isinstance(r.get("value"), dict) else {}
    return {"value": {k: v for k, v in value.items() if v not in (None, "", [])}, "answer": (r.get("answer") or "").strip(),
            "quote": r["quote"].strip(), "chunk": src}


@lru_cache(maxsize=512)
def _cached(p: str):
    return llm.chat([{"role": "user", "content": p}], as_json=True, timeout=20)


def best_sentence(question: str, chunk: dict) -> str | None:
    """Без ключа: предложение куска, где больше всего слов вопроса."""
    q = {w for w in lemmas(question) if len(w) > 2}
    best, score = None, 0
    for s in re.split(r"(?<=[.!?;])\s+|\n", chunk["text"]):
        s = s.strip(" •-–—*")
        if not 12 <= len(s) <= 300 or s.endswith("?"):
            continue
        n = len(q & set(lemmas(s)))
        if n > score:
            best, score = s, n
    return best if score else None
