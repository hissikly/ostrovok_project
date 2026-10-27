"""Ответы гостя по фильтрам поиска и отзывы об отеле. SQLite PROFILE_DB (по умолчанию data/runtime/profile.db, не в git).

Брони и «Так и было?» по обещанию живут в features/trip — здесь только то, чего там нет:
совпал ли отель с фильтром, с которым его выбирали, и мнение гостя своими словами.
"""
import datetime as dt
import json
import os
import sqlite3
import threading
from pathlib import Path

from core.config import DATA

DB = Path(os.getenv("PROFILE_DB", DATA / "runtime" / "profile.db"))
_lock = threading.RLock()   # одно соединение на все потоки, как в trip
_con = None


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def con():
    global _con
    with _lock:
        if _con is None:
            DB.parent.mkdir(parents=True, exist_ok=True)
            _con = sqlite3.connect(DB, check_same_thread=False)
            _con.row_factory = sqlite3.Row
            _con.executescript("""
                create table if not exists lens_answers (
                    booking_id text, hotel_id text, lens text, title text, claim text, answer text, created_at text,
                    primary key (booking_id, lens));
                create table if not exists reviews (
                    booking_id text primary key, hotel_id text, stars integer, text text, demo integer, created_at text);
                create table if not exists demo_trips (booking_id text primary key);""")
            # демо-отзывы без брони (booking_id "demo:…"): когда ездили и что подтвердили — в extra
            if "extra" not in {r[1] for r in _con.execute("pragma table_info(reviews)")}:
                _con.execute("alter table reviews add column extra text")
    return _con


def lens_answers(booking_id: str | None = None) -> list[dict]:
    with _lock:
        rows = (con().execute("select * from lens_answers where booking_id=?", (booking_id,)) if booking_id
                else con().execute("select * from lens_answers"))
        return [dict(r) for r in rows.fetchall()]


def add_lens_answer(booking_id: str, hotel_id: str, lens: str, title: str, claim: str, answer: str) -> None:
    """Повторный ответ по тому же фильтру не принимается — как в «Так и было?»."""
    with _lock:
        con().execute("insert or ignore into lens_answers values (?,?,?,?,?,?,?)",
                      (booking_id, hotel_id, lens, title, claim, answer, now()))
        con().commit()


def review(booking_id: str) -> dict | None:
    with _lock:
        r = con().execute("select stars, text, demo, created_at from reviews where booking_id=?", (booking_id,)).fetchone()
        return dict(r) if r else None


def save_review(booking_id: str, hotel_id: str, stars: int, text: str, demo: bool = False,
                extra: dict | None = None, created_at: str | None = None) -> None:
    with _lock:
        # демо-отзыв, переписанный гостем, остаётся помеченным демо
        con().execute("""insert into reviews (booking_id, hotel_id, stars, text, demo, created_at, extra)
                         values (?,?,?,?,?,?,?) on conflict(booking_id) do update set
                         stars=excluded.stars, text=excluded.text, created_at=excluded.created_at""",
                      (booking_id, hotel_id, stars, text, int(demo), created_at or now(),
                       json.dumps(extra, ensure_ascii=False) if extra else None))
        con().commit()


def hotel_reviews(hotel_id: str) -> list[dict]:
    with _lock:
        rows = con().execute("select * from reviews where hotel_id=? order by created_at desc", (hotel_id,)).fetchall()
    return [{**dict(r), "extra": json.loads(r["extra"]) if r["extra"] else None} for r in rows]


def has_demo_reviews() -> bool:
    with _lock:
        return con().execute("select 1 from reviews where booking_id like 'demo:%' limit 1").fetchone() is not None


def demo_bookings() -> set[str]:
    with _lock:
        return {r[0] for r in con().execute("select booking_id from demo_trips")}


def mark_demo(booking_id: str) -> None:
    with _lock:
        con().execute("insert or ignore into demo_trips values (?)", (booking_id,))
        con().commit()
