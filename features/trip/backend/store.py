"""Брони и ответы гостей «Так и было?». SQLite TRIP_DB (по умолчанию data/runtime/trip.db, не в git).

Бронь — мок: цены и оплаты нет, сохраняем выбор гостя (сторона, этаж, месяц), пожелание отелю,
обещание (факты, на которых держался выбор) и ответ отеля.
Ответ гостя — строка на каждый пункт обещания; demo=1 — имитированные ответы для показа.
"""
import datetime as dt
import json
import os
import secrets
import sqlite3
import threading
from pathlib import Path

from core.config import DATA

DB = Path(os.getenv("TRIP_DB", DATA / "runtime" / "trip.db"))
_lock = threading.RLock()   # одно соединение на все потоки, как в hotelier
_con = None
JSON_COLS = ("wish", "promise", "guests")


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
                create table if not exists bookings (
                    id text primary key, hotel_id text, month integer, facade text, floor integer,
                    wish text, promise text, status text, hotel_reply text, replied_at text,
                    finished_at text, created_at text);
                create index if not exists b_hotel on bookings(hotel_id, created_at);
                create table if not exists feedback (
                    id integer primary key, booking_id text, hotel_id text, fact_id text, characteristic text,
                    label text, answer text, base_confidence real, demo integer, created_at text);
                create index if not exists f_fact on feedback(hotel_id, fact_id);""")
            # кто едет (features/guests) — колонка добавлена позже, старые базы дополняем
            if "guests" not in {r[1] for r in _con.execute("pragma table_info(bookings)")}:
                _con.execute("alter table bookings add column guests text")
    return _con


def _row(r) -> dict | None:
    if r is None:
        return None
    d = dict(r)
    for k in JSON_COLS:
        d[k] = json.loads(d[k]) if d.get(k) else None
    return d


def create_booking(hotel_id: str, month: int, facade: str | None, floor: int | None, wish: dict, promise: list,
                   guests: dict | None = None) -> dict:
    bid = secrets.token_hex(3)
    with _lock:
        con().execute("""insert into bookings (id, hotel_id, month, facade, floor, wish, promise, guests, status, created_at)
                         values (?,?,?,?,?,?,?,?,'sent',?)""",
                      (bid, hotel_id, month, facade, floor, json.dumps(wish, ensure_ascii=False),
                       json.dumps(promise, ensure_ascii=False), json.dumps(guests or {"adults": 2, "children": []}), now()))
        con().commit()
    return get_booking(bid)


def get_booking(bid: str) -> dict | None:
    with _lock:
        return _row(con().execute("select * from bookings where id=?", (bid,)).fetchone())


def bookings(hotel_id: str | None = None) -> list[dict]:
    with _lock:
        rows = (con().execute("select * from bookings where hotel_id=? order by created_at desc", (hotel_id,))
                if hotel_id else con().execute("select * from bookings order by created_at desc"))
        return [_row(r) for r in rows.fetchall()]


def reply(bid: str, status: str, text: str) -> dict | None:
    with _lock:
        con().execute("update bookings set status=?, hotel_reply=?, replied_at=? where id=?", (status, text, now(), bid))
        con().commit()
    return get_booking(bid)


def finish(bid: str) -> None:
    with _lock:
        con().execute("update bookings set finished_at=? where id=?", (now(), bid))
        con().commit()


def add_feedback(rows: list[dict]) -> None:
    with _lock:
        con().executemany("""insert into feedback (booking_id, hotel_id, fact_id, characteristic, label, answer,
                             base_confidence, demo, created_at) values
                             (:booking_id, :hotel_id, :fact_id, :characteristic, :label, :answer,
                              :base_confidence, :demo, :created_at)""", rows)
        con().commit()


def feedback_rows(hotel_id: str | None = None, booking_id: str | None = None) -> list[dict]:
    sql, args = "select * from feedback where 1=1", []
    if hotel_id:
        sql, args = sql + " and hotel_id=?", args + [hotel_id]
    if booking_id:
        sql, args = sql + " and booking_id=?", args + [booking_id]
    with _lock:
        return [dict(r) for r in con().execute(sql + " order by id", args).fetchall()]


def has_demo() -> bool:
    with _lock:
        return con().execute("select 1 from feedback where demo=1 limit 1").fetchone() is not None
