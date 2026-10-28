"""Характеристики во время работы сервиса: добавленные описанием, их прогоны, факты и трассы.

Добавленные спеки и результаты прогонов лежат в таблице characteristics единой базы (core/db) и
переживают перезапуск. Встроенные «да / нет» (Wi-Fi) считаются при старте в фоне, без вопросов отелям.
Факты отдаются в общее хранилище (features/facts, register_provider), линзы — в поиск (features/search):
новая характеристика сразу видна в «Ещё фильтры», в «✨ опиши» и в карточке отеля.
"""
import datetime as dt
import json
import logging
import threading
import time

from core import db
from features.facts.backend import refresh as refresh_facts
from features.hotels.backend import hotel, hotels

from .planner import characteristic, research
from .spec import builtin, validate

log = logging.getLogger(__name__)
SCHEMA = "create table if not exists characteristics (id text primary key, spec text, results text, updated_at text)"
_lock = threading.Lock()
_custom: dict[str, dict] = {}     # id → спека, добавленная описанием
_results: dict[str, dict] = {}    # id → {run_at, facts: {hotel_id: fact}, traces: {hotel_id: [...]}, asked: [...]}
_jobs: dict[str, dict] = {}       # id → прогресс прогона


def all_specs() -> list[dict]:
    return builtin() + list(_custom.values())


def get_spec(cid: str) -> dict | None:
    return next((s for s in all_specs() if s["id"] == cid), None)


def runnable(s: dict) -> bool:
    """Что считает сам агент: добавленное описанием и встроенные «да / нет». Остальное считают другие фичи."""
    return s.get("origin") not in ("nearby",) and s["kind"] != "computed"


# --- хранение ---------------------------------------------------------------------------------------

def _db():
    db.schema("characteristics", SCHEMA)
    return db


def load():
    try:
        rows = _db().all("select id, spec, results from characteristics")
    except db.Unavailable:
        log.warning("characteristics: база недоступна, добавленные характеристики подгружу позже")
        return
    for r in rows:
        try:
            _custom[r["id"]] = json.loads(r["spec"])
            if r["results"]:
                _results[r["id"]] = json.loads(r["results"])
        except ValueError as e:
            log.warning("characteristics: не прочитал %s (%s)", r["id"], e)


def _save_spec(s):
    _db().run("""insert into characteristics (id, spec, updated_at) values (?,?,?)
                 on conflict(id) do update set spec=excluded.spec, updated_at=excluded.updated_at""",
              (s["id"], json.dumps(s, ensure_ascii=False), s["created_at"]))


def _save_results(cid):
    _db().run("update characteristics set results=?, updated_at=? where id=?",
              (json.dumps(_results[cid], ensure_ascii=False), _results[cid]["run_at"], cid))


def add(spec: dict) -> tuple[dict | None, list[str], list[str]]:
    taken = {s["id"] for s in all_specs()}
    s, errors, warnings = validate(spec, taken)
    if errors:
        return None, errors, warnings
    s["created_at"] = dt.datetime.now().isoformat(timespec="seconds")
    with _lock:
        _save_spec(s)          # сначала в базу: не записалось — характеристики нет и в памяти
        _custom[s["id"]] = s
    register_lens(s)
    return s, errors, warnings


def remove(cid: str) -> bool:
    if cid not in _custom:
        return False
    with _lock:
        _db().run("delete from characteristics where id=?", (cid,))
        _custom.pop(cid)
        _results.pop(cid, None)
    unregister_lens(cid)
    refresh_facts()
    return True


# --- прогон по всем отелям --------------------------------------------------------------------------

def run(cid: str, ask: bool = True) -> dict:
    """Запустить прогон в фоне; повторный запуск, пока идёт прошлый, просто вернёт его прогресс."""
    s = get_spec(cid)
    if s is None or not runnable(s):
        return {"error": "not runnable"}
    job = _jobs.get(cid)
    if job and job["state"] == "running":
        return job
    hs = hotels()
    _jobs[cid] = job = {"id": cid, "state": "running", "done": 0, "total": len(hs), "answered": 0, "asked": 0,
                        "unknown": 0, "started_at": dt.datetime.now().isoformat(timespec="seconds")}
    threading.Thread(target=_run, args=(s, hs, job, ask), daemon=True).start()
    return job


def _run(s, hs, job, ask):
    t0 = time.time()
    try:
        prev = _results.get(s["id"], {})
        asked = set(prev.get("asked", []))
        facts, traces = {}, {}
        for h in hs:
            r = research(h, s, ask=ask, asked_before=h["id"] in asked)
            traces[h["id"]] = r["trace"]
            if r["fact"]:
                facts[h["id"]] = r["fact"]
            if any(t["tool"] == "ask_hotelier" and t["status"] == "asked" for t in r["trace"]):
                asked.add(h["id"])
            job[r["state"]] += 1
            job["done"] += 1
        with _lock:
            _results[s["id"]] = {"run_at": dt.datetime.now().isoformat(timespec="seconds"), "facts": facts,
                                 "traces": traces, "asked": sorted(asked)}
            if s.get("origin") != "builtin":
                _save_results(s["id"])
        refresh_facts()
        job.update(state="done", seconds=round(time.time() - t0, 1))
        log.info("characteristics: %s по %d отелям за %.1f с: ответ %d, спросили %d, не знаем %d", s["id"],
                 len(hs), time.time() - t0, job["answered"], job["asked"], job["unknown"])
    except Exception as e:
        log.exception("characteristics: прогон %s упал", s["id"])
        job.update(state="error", error=str(e))


def status(cid: str) -> dict | None:
    if cid in _jobs:
        return _jobs[cid]
    r = _results.get(cid)
    if r:
        n = len(r["traces"])
        return {"id": cid, "state": "done", "done": n, "total": n, "answered": len(r["facts"]),
                "asked": len(r.get("asked", [])), "run_at": r["run_at"]}
    return None


def startup():
    """Встроенные «да / нет» считаем в фоне при старте — без вопросов отелям."""
    for s in builtin():
        if runnable(s) and s["id"] not in _results:
            run(s["id"], ask=False)


# --- факты и трассы для остальных фич -------------------------------------------------------------------

def facts() -> list[dict]:
    return [f for r in list(_results.values()) for f in r["facts"].values()]


def trace(cid: str, hotel_id: str) -> list[dict] | None:
    r = _results.get(cid)
    return r["traces"].get(hotel_id) if r else None


def hotel_view(hotel_id: str) -> list[dict]:
    """Что агент узнал об отеле по характеристикам, которые считает сам: ответ, уверенность, трасса."""
    out = []
    for s in all_specs():
        r = _results.get(s["id"])
        if not runnable(s) or not r or hotel_id not in r["traces"]:
            continue
        f = r["facts"].get(hotel_id)
        out.append({"id": s["id"], "title": s["title"], "icon": s.get("icon"), "origin": s.get("origin"),
                    "fact": f, "text": (f or {}).get("value", {}).get("text") or _near_text(f),
                    "state": "answered" if f else ("asked" if hotel_id in r.get("asked", []) else "unknown"),
                    "trace": r["traces"][hotel_id]})
    return out


def _near_text(f):
    if not f:
        return None
    v = f["value"]
    if v.get("meters") is None:
        return f"{v['kind']}: в {v['within_min']} мин пешком не нашли"
    name = f" «{v['name']}»" if v.get("name") else ""
    return f"{v['kind']}{name}, {v['walk_min']} мин пешком"


def places(hotel_id: str, cid: str) -> dict | None:
    """Места характеристики «рядом» на карте — в том же виде, что /api/hotels/{id}/nearby/{spec}."""
    from .geo import Finder
    s, h = get_spec(cid), hotel(hotel_id)
    if s is None or h is None or s["kind"] != "near" or s.get("origin") == "nearby":
        return None
    p = next(st["params"] for st in s["plan"] if st["tool"] == "poi_nearby")
    items = Finder(p["osm"], p["partial_min"]).all_near(h["lat"], h["lon"])
    return {"spec": cid, "title": s["title"], "kind": p["kind"], "within_min": p["partial_min"],
            "items": [{**it, "kind": p["kind"]} for it in items]}


# --- линзы поиска -------------------------------------------------------------------------------------------

def _lens_fn(s):
    from features.search.backend.lenses import MATCH, NO, PARTIAL, UNKNOWN, _res

    def fn(facts_, ctx):
        f = next((f for f in facts_ if f["characteristic"] in (f"near:{s['id']}", f"custom:{s['id']}")
                  and f["status"] == "active"), None)
        if f is None:
            asked = s["id"] in _results and facts_ and facts_[0]["hotel_id"] in _results[s["id"]].get("asked", [])
            return _res(UNKNOWN, f"{s['title']}: спросили у отеля" if asked else f"{s['title']}: пока не знаем", [])
        v = f["value"]
        text = v.get("text") or _near_text(f)
        if s["kind"] == "near":
            p = next(st["params"] for st in s["plan"] if st["tool"] == "poi_nearby")
            far = s.get("prefer") == "far"
            if v.get("meters") is None:
                state = MATCH if far else NO
            elif v["walk_min"] <= p["match_min"]:
                state = NO if far else MATCH
            else:
                state = PARTIAL
            r = _res(state, text, [f])
            if v.get("meters") is not None and not far:
                r["point"] = {"lat": v["lat"], "lon": v["lon"], "name": text}
            return r
        ans = v.get("answer")
        return _res(MATCH if ans is True else NO if ans is False else PARTIAL, text, [f])
    return fn


def register_lens(s):
    """Линза в «Ещё фильтры» и словарь «✨ опиши» — без правки кода поиска."""
    from features.search.backend.lenses import BY_ID, LENSES
    if not runnable(s):
        return
    lid = f"near_{s['id']}" if characteristic(s).startswith("near:") else f"char_{s['id']}"
    hint = ("По открытой карте OSM, время пешком по улицам" if s["kind"] == "near"
            else "Отметки отеля на карте, его ответы и сайт; не знаем — спрашиваем у отеля")
    lens = {"id": lid, "title": s["title"], "icon": s.get("icon", "pin"), "fn": _lens_fn(s), "primary": False,
            "group": s.get("group", "Прочее"), "synonyms": s.get("synonyms") or [s["title"].lower()], "hint": hint,
            "agent": True}
    unregister_lens(s["id"])
    LENSES.append(lens)
    BY_ID[lid] = lens


def unregister_lens(cid):
    from features.search.backend.lenses import BY_ID, LENSES
    for lid in (f"near_{cid}", f"char_{cid}"):
        l = BY_ID.get(lid)
        if l and l.get("agent"):
            LENSES.remove(l)
            BY_ID.pop(lid)


def register_lenses():
    for s in all_specs():
        register_lens(s)
