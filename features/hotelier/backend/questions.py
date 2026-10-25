"""Очередь вопросов отелю.

Гость нажал «Спросить у отеля» — вопрос не отправляется второй раз, если такой уже ждёт ответа:
тот же отель + та же тема (или тот же смысл фразы, если темы нет) → только растёт счётчик гостей.
Отельер видит один вопрос «48 гостей спрашивали», а не 48 писем.
Хранение — SQLite HOTELIER_DB (по умолчанию data/runtime/hotelier.db, не в git).
"""
import datetime as dt
import os
import sqlite3
import threading
from pathlib import Path

from core.config import DATA
from core.textmatch import STOP, lemmas
from features.knowledge.backend import topics

DB = Path(os.getenv("HOTELIER_DB", DATA / "runtime" / "hotelier.db"))
_lock = threading.Lock()
_con = None


def con():
    global _con
    if _con is None:
        DB.parent.mkdir(parents=True, exist_ok=True)
        _con = sqlite3.connect(DB, check_same_thread=False)
        _con.row_factory = sqlite3.Row
        _con.execute("""create table if not exists questions (
            id integer primary key, hotel_id text, topic text, key text, text text, guest_text text,
            demand integer, origin text, status text, created_at text, updated_at text)""")
        _con.execute("create index if not exists q_hotel on questions(hotel_id, status)")
    return _con


def _key(topic: str | None, text: str) -> str:
    """Тема, а без темы — смысл фразы: начальные формы значимых слов по алфавиту."""
    return f"topic:{topic}" if topic else "text:" + " ".join(sorted({w for w in lemmas(text) if w not in STOP}))


def _hotel_text(topic: str | None, guest_text: str) -> str:
    t = next((t for t in topics() if t["id"] == topic), None) if topic else None
    if t and t.get("ask_hotel"):
        return t["ask_hotel"]
    s = guest_text.strip().rstrip("?.! ")
    return (s[:1].upper() + s[1:] + "?") if s else ""


def ask_hotel(hotel_id: str, topic: str | None, guest_text: str, origin: str = "guest") -> dict:
    now = dt.datetime.now().isoformat(timespec="seconds")
    key = _key(topic, guest_text)
    with _lock:
        c = con()
        r = c.execute("select * from questions where hotel_id=? and key=? and status='open'", (hotel_id, key)).fetchone()
        if r:
            c.execute("update questions set demand=demand+1, updated_at=? where id=?", (now, r["id"]))
            created = False
            qid = r["id"]
        else:
            cur = c.execute("""insert into questions (hotel_id, topic, key, text, guest_text, demand, origin, status,
                               created_at, updated_at) values (?,?,?,?,?,1,?,'open',?,?)""",
                            (hotel_id, topic, key, _hotel_text(topic, guest_text), guest_text, origin, now, now))
            created, qid = True, cur.lastrowid
        c.commit()
        q = dict(c.execute("select * from questions where id=?", (qid,)).fetchone())
    return {**q, "created": created}


def open_questions(hotel_id: str) -> list[dict]:
    return [dict(r) for r in con().execute(
        "select * from questions where hotel_id=? and status='open' order by demand desc, id", (hotel_id,)).fetchall()]
