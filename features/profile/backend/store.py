"""Ответы гостя по фильтрам поиска и отзывы об отеле. Таблицы в единой базе (core/db: PostgreSQL или SQLite).

Брони и «Так и было?» по обещанию живут в features/trip — здесь только то, чего там нет:
совпал ли отель с фильтром, с которым его выбирали, и мнение гостя своими словами.
"""
import datetime as dt
import json

from core import db

# демо-отзывы без брони (booking_id "demo:…"): когда ездили и что подтвердили — в extra
SCHEMA = """
    create table if not exists lens_answers (
        booking_id text, hotel_id text, lens text, title text, claim text, answer text, created_at text,
        primary key (booking_id, lens));
    create table if not exists reviews (
        booking_id text primary key, hotel_id text, stars integer, text text, demo integer, created_at text, extra text);
    create index if not exists r_hotel on reviews(hotel_id, created_at);
    create table if not exists demo_trips (booking_id text primary key)"""


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _db():
    db.schema("profile", SCHEMA)
    return db


def lens_answers(booking_id: str | None = None) -> list[dict]:
    return (_db().all("select * from lens_answers where booking_id=?", (booking_id,)) if booking_id
            else _db().all("select * from lens_answers"))


def add_lens_answer(booking_id: str, hotel_id: str, lens: str, title: str, claim: str, answer: str) -> None:
    """Повторный ответ по тому же фильтру не принимается — как в «Так и было?»."""
    _db().run("insert into lens_answers values (?,?,?,?,?,?,?) on conflict do nothing",
              (booking_id, hotel_id, lens, title, claim, answer, now()))


def review(booking_id: str) -> dict | None:
    return _db().one("select stars, text, demo, created_at from reviews where booking_id=?", (booking_id,))


def save_review(booking_id: str, hotel_id: str, stars: int, text: str, demo: bool = False,
                extra: dict | None = None, created_at: str | None = None) -> None:
    # демо-отзыв, переписанный гостем, остаётся помеченным демо
    _db().run("""insert into reviews (booking_id, hotel_id, stars, text, demo, created_at, extra)
                 values (?,?,?,?,?,?,?) on conflict(booking_id) do update set
                 stars=excluded.stars, text=excluded.text, created_at=excluded.created_at""",
              (booking_id, hotel_id, stars, text, int(demo), created_at or now(),
               json.dumps(extra, ensure_ascii=False) if extra else None))


def hotel_reviews(hotel_id: str) -> list[dict]:
    rows = _db().all("select * from reviews where hotel_id=? order by created_at desc", (hotel_id,))
    return [{**r, "extra": json.loads(r["extra"]) if r["extra"] else None} for r in rows]


def demo_bookings() -> set[str]:
    return {r["booking_id"] for r in _db().all("select booking_id from demo_trips")}


def mark_demo(booking_id: str) -> None:
    _db().run("insert into demo_trips values (?) on conflict do nothing", (booking_id,))
