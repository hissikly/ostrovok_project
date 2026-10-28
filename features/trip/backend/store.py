"""Брони и ответы гостей «Так и было?». Таблицы в единой базе (core/db: PostgreSQL или SQLite).

Бронь — мок: цены и оплаты нет, сохраняем выбор гостя (сторона, этаж, месяц), пожелание отелю,
обещание (факты, на которых держался выбор) и ответ отеля.
Ответ гостя — строка на каждый пункт обещания; demo=1 — имитированные ответы для показа.
"""
import datetime as dt
import json
import secrets

from core import db

JSON_COLS = ("wish", "promise", "guests", "lenses")
# guests — кто едет (features/guests); lenses — фильтры поиска, с которыми гость выбрал отель (features/profile)
SCHEMA = """
    create table if not exists bookings (
        id text primary key, hotel_id text, month integer, facade text, floor integer,
        wish text, promise text, status text, hotel_reply text, replied_at text,
        finished_at text, created_at text, guests text, lenses text);
    create index if not exists b_hotel on bookings(hotel_id, created_at);
    create table if not exists feedback (
        id {id}, booking_id text, hotel_id text, fact_id text, characteristic text,
        label text, answer text, base_confidence real, demo integer, created_at text);
    create index if not exists f_fact on feedback(hotel_id, fact_id)"""
FEEDBACK_COLS = ("booking_id", "hotel_id", "fact_id", "characteristic", "label", "answer", "base_confidence", "demo",
                 "created_at")


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _db():
    db.schema("trip", SCHEMA)
    return db


def _row(r) -> dict | None:
    if r is None:
        return None
    for k in JSON_COLS:
        r[k] = json.loads(r[k]) if r.get(k) else None
    return r


def create_booking(hotel_id: str, month: int, facade: str | None, floor: int | None, wish: dict, promise: list,
                   guests: dict | None = None, lenses: list[str] | None = None) -> dict:
    bid = secrets.token_hex(3)
    _db().run("""insert into bookings (id, hotel_id, month, facade, floor, wish, promise, guests, lenses, status, created_at)
                 values (?,?,?,?,?,?,?,?,?,'sent',?)""",
              (bid, hotel_id, month, facade, floor, json.dumps(wish, ensure_ascii=False),
               json.dumps(promise, ensure_ascii=False), json.dumps(guests or {"adults": 2, "children": []}),
               json.dumps(lenses or []), now()))
    return get_booking(bid)


def get_booking(bid: str) -> dict | None:
    return _row(_db().one("select * from bookings where id=?", (bid,)))


def bookings(hotel_id: str | None = None) -> list[dict]:
    rows = (_db().all("select * from bookings where hotel_id=? order by created_at desc", (hotel_id,))
            if hotel_id else _db().all("select * from bookings order by created_at desc"))
    return [_row(r) for r in rows]


def reply(bid: str, status: str, text: str) -> dict | None:
    _db().run("update bookings set status=?, hotel_reply=?, replied_at=? where id=?", (status, text, now(), bid))
    return get_booking(bid)


def backdate(bid: str, created_at: str, finished_at: str | None) -> None:
    """Демо прошлых поездок (features/profile): бронь сделана и поездка завершена в прошлом."""
    _db().run("update bookings set created_at=?, finished_at=? where id=?", (created_at, finished_at, bid))


def finish(bid: str) -> None:
    _db().run("update bookings set finished_at=? where id=?", (now(), bid))


def add_feedback(rows: list[dict]) -> None:
    with _db().tx() as t:
        t.many(f"insert into feedback ({', '.join(FEEDBACK_COLS)}) values ({', '.join('?' * len(FEEDBACK_COLS))})",
               [[r[c] for c in FEEDBACK_COLS] for r in rows])


def feedback_rows(hotel_id: str | None = None, booking_id: str | None = None) -> list[dict]:
    sql, args = "select * from feedback where 1=1", []
    if hotel_id:
        sql, args = sql + " and hotel_id=?", args + [hotel_id]
    if booking_id:
        sql, args = sql + " and booking_id=?", args + [booking_id]
    return _db().all(sql + " order by id", args)


def has_demo() -> bool:
    return _db().one("select 1 as x from feedback where demo=1 limit 1") is not None
