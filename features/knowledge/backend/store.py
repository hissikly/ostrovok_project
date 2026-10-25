"""База знаний по уровням места: ru → ru/krd → ru/krd/sochi → ru/krd/sochi/<hotel_id>.

- Верхние уровни (страна, край, город) — из демо-данных data/seed/knowledge.json (только чтение).
- Ответы отелей пишутся на лету в SQLite (KNOWLEDGE_DB, по умолчанию data/runtime/knowledge.db):
  новая запись по той же теме не стирает старую, а делает её superseded — история остаётся.
"""
import datetime as dt
import json
import os
import sqlite3
import threading
from functools import lru_cache
from pathlib import Path

from core.config import DATA
from core.seed import load

CITY = "ru/krd/sochi"
DB = Path(os.getenv("KNOWLEDGE_DB", DATA / "runtime" / "knowledge.db"))
_lock = threading.Lock()


def hotel_path(hotel_id: str) -> str:
    # районов (Центр, Хоста, Адлер) пока нет — отель сразу под городом
    return f"{CITY}/{hotel_id}"


def levels(path: str) -> list[str]:
    """ru/krd/sochi/w1 → [ru/krd/sochi/w1, ru/krd/sochi, ru/krd, ru] — снизу вверх."""
    parts = path.split("/")
    return ["/".join(parts[:i]) for i in range(len(parts), 0, -1)]


@lru_cache(maxsize=1)
def _seed() -> dict:
    out = {}
    for k in load("knowledge.json") or []:
        out[(k["path"], k["topic"])] = {**k, "status": "active"}
    return out


def _db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("""create table if not exists knowledge (
        id integer primary key, path text, topic text, value text, text text, source text,
        confidence real, obtained_at text, valid_until text, evidence text, status text)""")
    con.execute("create index if not exists k_path_topic on knowledge(path, topic, status)")
    return con


_con = None


def con():
    global _con
    if _con is None:
        _con = _db()
    return _con


def _row(r) -> dict:
    d = dict(r)
    d["value"], d["evidence"] = json.loads(d["value"] or "null"), json.loads(d["evidence"] or "{}")
    return d


def get(path: str, topic: str) -> dict | None:
    """Знание ровно этого уровня: сначала записанное на лету (ответ отеля), потом демо-данные."""
    r = con().execute("select * from knowledge where path=? and topic=? and status='active' order by id desc limit 1",
                      (path, topic)).fetchone()
    if r:
        return _row(r)
    return _seed().get((path, topic))


def lookup(path: str, topic: str) -> dict | None:
    """Ответ снизу вверх: отель → город → край → страна. Возвращает знание + на каком уровне нашли."""
    for p in levels(path):
        k = get(p, topic)
        if k:
            return {**k, "level": level_name(p)}
    return None


def level_name(path: str) -> str:
    n = len(path.split("/"))
    return {1: "country", 2: "region", 3: "city"}.get(n, "hotel")


def write(path: str, topic: str, value, text: str, source: str, confidence: float,
          evidence: dict | None = None, valid_days: int = 365) -> dict:
    today = dt.date.today()
    with _lock:
        c = con()
        c.execute("update knowledge set status='superseded' where path=? and topic=? and status='active'", (path, topic))
        cur = c.execute("""insert into knowledge (path, topic, value, text, source, confidence, obtained_at, valid_until,
                           evidence, status) values (?,?,?,?,?,?,?,?,?, 'active')""",
                        (path, topic, json.dumps(value, ensure_ascii=False), text, source, confidence,
                         today.isoformat(), (today + dt.timedelta(days=valid_days)).isoformat(),
                         json.dumps(evidence or {}, ensure_ascii=False)))
        c.commit()
        return _row(c.execute("select * from knowledge where id=?", (cur.lastrowid,)).fetchone())


def history(path: str, topic: str) -> list[dict]:
    return [_row(r) for r in con().execute(
        "select * from knowledge where path=? and topic=? order by id", (path, topic)).fetchall()]
