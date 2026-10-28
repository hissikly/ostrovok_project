"""Очередь вопросов отелю.

Гость нажал «Спросить у отеля» — вопрос не отправляется второй раз, если такой уже ждёт ответа:
тот же отель + та же тема (или тот же смысл фразы, если темы нет) → только растёт счётчик гостей.
Отельер видит один вопрос «48 гостей спрашивали», а не 48 писем.
Хранение — таблица questions единой базы (core/db: PostgreSQL или SQLite).
"""
import datetime as dt

from core import db
from core.textmatch import meaning_key
from features.knowledge.backend import topics

SCHEMA = """
    create table if not exists questions (
        id {id}, hotel_id text, topic text, key text, text text, guest_text text,
        demand integer, origin text, status text, created_at text, updated_at text);
    create index if not exists q_hotel on questions(hotel_id, status)"""


def _db():
    db.schema("hotelier", SCHEMA)
    return db


def _key(topic: str | None, text: str) -> str:
    """Тема, а без темы — смысл фразы: начальные формы значимых слов по алфавиту."""
    return f"topic:{topic}" if topic else "text:" + meaning_key(text)


def _hotel_text(topic: str | None, guest_text: str) -> str:
    t = next((t for t in topics() if t["id"] == topic), None) if topic else None
    if t and t.get("ask_hotel"):
        return t["ask_hotel"]
    s = guest_text.strip().rstrip("?.! ")
    return (s[:1].upper() + s[1:] + "?") if s else ""


def ask_hotel(hotel_id: str, topic: str | None, guest_text: str, origin: str = "guest") -> dict:
    now = dt.datetime.now().isoformat(timespec="seconds")
    key = _key(topic, guest_text)
    with _db().tx() as t:      # найти открытый и прибавить гостя или создать — одной транзакцией
        r = t.one("select id from questions where hotel_id=? and key=? and status='open'", (hotel_id, key))
        if r:
            t.run("update questions set demand=demand+1, updated_at=? where id=?", (now, r["id"]))
            q, created = t.one("select * from questions where id=?", (r["id"],)), False
        else:
            q = t.one("""insert into questions (hotel_id, topic, key, text, guest_text, demand, origin, status,
                         created_at, updated_at) values (?,?,?,?,?,1,?,'open',?,?) returning *""",
                      (hotel_id, topic, key, _hotel_text(topic, guest_text), guest_text, origin, now, now))
            created = True
    return {**q, "created": created}


def open_questions(hotel_id: str) -> list[dict]:
    return _db().all("select * from questions where hotel_id=? and status='open' order by demand desc, id", (hotel_id,))


def asked(hotel_id: str, topic: str) -> bool:
    """Вопрос по теме уже задавали (открыт или закрыт)."""
    return _db().one("select 1 as x from questions where hotel_id=? and topic=? limit 1", (hotel_id, topic)) is not None


def get_question(qid: int) -> dict | None:
    return _db().one("select * from questions where id=?", (qid,))


def close(qid: int) -> None:
    _db().run("update questions set status='answered', updated_at=? where id=?",
              (dt.datetime.now().isoformat(timespec="seconds"), qid))


def demand_total(hotel_id: str) -> int:
    r = _db().one("select coalesce(sum(demand), 0) as n from questions where hotel_id=? and status='open'", (hotel_id,))
    return int(r["n"])
