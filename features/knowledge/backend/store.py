"""База знаний по уровням места: ru → ru/krd → ru/krd/sochi → ru/krd/sochi/<hotel_id>.

- Верхние уровни (страна, край, город) — демо-данные data/seed/knowledge.json, при первом запуске копируются в базу.
- Ответы отелей пишутся на лету в таблицу knowledge единой базы (core/db: PostgreSQL или SQLite):
  новая запись по той же теме не стирает старую, а делает её superseded — история остаётся.
"""
import datetime as dt
import json
from functools import lru_cache

from core import db
from core.seed import load

CITY = "ru/krd/sochi"
SCHEMA = """
    create table if not exists knowledge (
        id {id}, path text, topic text, value text, text text, source text,
        confidence real, obtained_at text, valid_until text, evidence text, status text);
    create index if not exists k_path_topic on knowledge(path, topic, status)"""


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


def _seed_rows(t) -> None:
    """Знания страны/края/города из демо-данных — в ту же таблицу, если их там ещё нет."""
    for k in _seed().values():
        if not t.one("select id from knowledge where path=? and topic=? limit 1", (k["path"], k["topic"])):
            t.run("""insert into knowledge (path, topic, value, text, source, confidence, obtained_at, valid_until,
                     evidence, status) values (?,?,?,?,?,?,?,?,?, 'active')""",
                  (k["path"], k["topic"], json.dumps(k.get("value"), ensure_ascii=False), k.get("text"), k.get("source"),
                   k.get("confidence"), k.get("obtained_at"), k.get("valid_until"),
                   json.dumps(k.get("evidence") or {}, ensure_ascii=False)))


def _db():
    db.schema("knowledge", SCHEMA, init=_seed_rows)
    return db


def _row(r) -> dict:
    d = dict(r)
    d["value"], d["evidence"] = json.loads(d["value"] or "null"), json.loads(d["evidence"] or "{}")
    return d


def get(path: str, topic: str) -> dict | None:
    """Знание ровно этого уровня: сначала записанное на лету (ответ отеля), потом демо-данные."""
    r = _db().one("select * from knowledge where path=? and topic=? and status='active' order by id desc limit 1",
                  (path, topic))
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
    with _db().tx() as t:      # старая запись superseded и новая active — одной транзакцией
        t.run("update knowledge set status='superseded' where path=? and topic=? and status='active'", (path, topic))
        return _row(t.one("""insert into knowledge (path, topic, value, text, source, confidence, obtained_at, valid_until,
                             evidence, status) values (?,?,?,?,?,?,?,?,?, 'active') returning *""",
                          (path, topic, json.dumps(value, ensure_ascii=False), text, source, confidence,
                           today.isoformat(), (today + dt.timedelta(days=valid_days)).isoformat(),
                           json.dumps(evidence or {}, ensure_ascii=False))))


def history(path: str, topic: str) -> list[dict]:
    return [_row(r) for r in _db().all("select * from knowledge where path=? and topic=? order by id", (path, topic))]
