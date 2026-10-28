"""Единая база сервиса: брони, ответы гостей и отелей, вопросы отелю, база знаний, добавленные характеристики.

DB_URL=postgresql://… — PostgreSQL 16 (в docker-compose это сервис db). Без DB_URL — один файл SQLite
DATA/runtime/okno.db, чтобы сервис и тесты запускались без Docker. SQL у фич общий для обеих:
плейсхолдеры «?», «on conflict … do», «returning id»; в DDL «{id}» — автоинкрементный ключ.

База недоступна — бросаем Unavailable, app/main.py отвечает 503 «Временная ошибка», остальные экраны живут.
Соединение одно на процесс, под замком (нагрузка демо); оборвалось — переподключаемся на следующем запросе.
"""
import logging
import sqlite3
import threading
import time
from contextlib import contextmanager

from core.config import DATA, DB_URL

log = logging.getLogger(__name__)
PG = DB_URL.startswith(("postgres://", "postgresql://"))
FILE = DATA / "runtime" / "okno.db"
FIRST_WAIT = 30      # с: при старте база в соседнем контейнере может ещё подниматься
_lock = threading.RLock()
_con = None
_started = False
_ready: set[str] = set()     # какие схемы уже созданы в этом соединении


class Unavailable(Exception):
    """База не отвечает — временная ошибка, не баг."""


if PG:
    import psycopg
    from psycopg.rows import dict_row
    _BROKEN = (psycopg.OperationalError, psycopg.InterfaceError)
else:
    _BROKEN = (sqlite3.OperationalError,)


def _open():
    if PG:
        return psycopg.connect(DB_URL, row_factory=dict_row, connect_timeout=5)
    FILE.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(FILE, check_same_thread=False, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def _connect():
    global _con, _started
    if _con is not None:
        return _con
    deadline = time.time() + (0 if _started else FIRST_WAIT)
    while True:
        try:
            _con = _open()
            _started = True
            _ready.clear()
            log.info("db: подключились к %s", "PostgreSQL" if PG else FILE)
            return _con
        except _BROKEN as e:
            if time.time() >= deadline:
                _started = True
                log.warning("db: база недоступна (%s)", type(e).__name__)
                raise Unavailable from e
            time.sleep(1)


def _sql(sql: str) -> str:
    return sql.replace("?", "%s") if PG else sql


def _args(args) -> tuple:
    # PostgreSQL не хранит символ NUL в тексте (SQLite хранит) — вырезаем, иначе 500 на мусорном вводе
    return tuple(a.replace("\x00", "") if isinstance(a, str) else a for a in args)


class _Tx:
    def __init__(self, con):
        self.con = con

    def _cur(self, sql, args):
        return self.con.execute(_sql(sql), _args(args))

    def all(self, sql: str, args=()) -> list[dict]:
        return [dict(r) for r in self._cur(sql, args).fetchall()]

    def one(self, sql: str, args=()) -> dict | None:
        r = self._cur(sql, args).fetchone()
        return dict(r) if r is not None else None

    def run(self, sql: str, args=()) -> None:
        self._cur(sql, args)

    def many(self, sql: str, rows: list) -> None:
        if PG:
            with self.con.cursor() as cur:
                cur.executemany(_sql(sql), [_args(r) for r in rows])
        else:
            self.con.executemany(sql, [_args(r) for r in rows])


@contextmanager
def tx():
    """Транзакция: всё внутри — целиком или никак. Оборвалось соединение — Unavailable, переподключимся потом."""
    global _con
    with _lock:
        con = _connect()
        try:
            yield _Tx(con)
            con.commit()
        except _BROKEN as e:
            _con = None
            try:
                con.close()
            except Exception:  # noqa: BLE001 — соединение уже мёртвое
                pass
            log.warning("db: соединение оборвалось (%s)", type(e).__name__)
            raise Unavailable from e
        except BaseException:
            con.rollback()
            raise


def schema(name: str, ddl: str, init=None) -> None:
    """Создать таблицы фичи один раз на соединение (create … if not exists — повторно безопасно).
    init(t) — в той же транзакции дописать начальные строки (сама проверяет, нет ли их уже)."""
    if name in _ready:
        return
    ddl = ddl.replace("{id}", "bigserial primary key" if PG else "integer primary key")
    with tx() as t:
        for stmt in filter(None, (s.strip() for s in ddl.split(";"))):
            t.run(stmt)
        if init:
            init(t)
    _ready.add(name)


def all(sql: str, args=()) -> list[dict]:   # noqa: A001 — как у курсора
    with tx() as t:
        return t.all(sql, args)


def one(sql: str, args=()) -> dict | None:
    with tx() as t:
        return t.one(sql, args)


def run(sql: str, args=()) -> None:
    with tx() as t:
        t.run(sql, args)


def kind() -> str:
    return "postgresql" if PG else "sqlite"


def ping() -> bool:
    try:
        return one("select 1 as ok") is not None
    except Unavailable:
        return False

