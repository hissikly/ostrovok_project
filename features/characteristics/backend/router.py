from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from features.facts.backend import facts_for
from features.hotels.backend import hotel

from . import store
from .from_text import draft
from .planner import research
from .spec import human
from .tools import registry

router = APIRouter(prefix="/api", tags=["characteristics"])
router.add_event_handler("startup", store.startup)

# какой встроенной спеке принадлежит факт другой фичи
OWNER = {"sea_view": "sea_view", "sunset_view": "sunset_view", "beach_route": "beach_route",
         "beach_distance": "beach_route", "noise": "noise"}


class TextIn(BaseModel):
    text: str


class SpecIn(BaseModel):
    spec: dict
    run: bool = True


def _nf(what):
    return HTTPException(404, detail={"error": "not found", "detail": what})


def _brief(s):
    return {k: s.get(k) for k in ("id", "title", "question", "kind", "prefer", "icon", "group", "origin", "text",
                                  "created_at")} | {"plan": human(s), "tools": [st["tool"] for st in s["plan"]],
                                                    "runnable": store.runnable(s), "status": store.status(s["id"])}


@router.get("/characteristics")
def list_characteristics():
    """Все характеристики: встроенные, каталог «что рядом» и добавленные описанием."""
    return [_brief(s) for s in store.all_specs()]


@router.get("/characteristics/tools")
def tools():
    """Реестр инструментов агента — с описаниями, которые читает LLM."""
    return registry()


@router.post("/characteristics/from-text")
def from_text(q: TextIn):
    """Фраза → черновик спеки на подтверждение (ничего не сохраняет и не считает)."""
    if not q.text.strip():
        raise HTTPException(400, detail={"error": "empty text"})
    return draft(q.text, store.all_specs())


@router.post("/characteristics")
def add(q: SpecIn):
    """Сохранить подтверждённую спеку и сразу посчитать по всем отелям (в фоне)."""
    s, errors, warnings = store.add(q.spec)
    if errors:
        raise HTTPException(400, detail={"error": "invalid spec", "detail": errors})
    job = store.run(s["id"]) if q.run else None
    return {"spec": s, "warnings": warnings, "status": job}


@router.get("/characteristics/{cid}")
def get(cid: str):
    s = store.get_spec(cid)
    if s is None:
        raise _nf(cid)
    return {**_brief(s), "spec": s}


@router.post("/characteristics/{cid}/run")
def run(cid: str):
    if store.get_spec(cid) is None:
        raise _nf(cid)
    job = store.run(cid)
    if "error" in job:
        raise HTTPException(400, detail={"error": "not runnable", "detail": "эту характеристику считает своя фича"})
    return job


@router.get("/characteristics/{cid}/status")
def status(cid: str):
    st = store.status(cid)
    if st is None:
        raise _nf(cid)
    return st


@router.delete("/characteristics/{cid}")
def remove(cid: str):
    if not store.remove(cid):
        raise HTTPException(400, detail={"error": "only custom characteristics can be removed", "detail": cid})
    return {"removed": cid}


@router.get("/hotels/{hotel_id}/agent")
def hotel_agent(hotel_id: str):
    """Что агент узнал об отеле по своим характеристикам — ответ и трасса поиска."""
    if hotel(hotel_id) is None:
        raise _nf(hotel_id)
    return store.hotel_view(hotel_id)


@router.get("/facts/{fact_id}/trace")
def fact_trace(fact_id: str):
    """Как агент пришёл к факту: какие источники пробовал и что каждый сказал."""
    hotel_id = fact_id.split(":", 1)[0]
    f = next((f for f in facts_for(hotel_id) if f["id"] == fact_id), None)
    h = hotel(hotel_id)
    if f is None or h is None:
        raise _nf(fact_id)
    char = f["characteristic"]
    if "agent" in (f.get("evidence") or {}):
        cid = f["evidence"]["spec"]
        return {"fact": fact_id, "spec": cid, "trace": store.trace(cid, hotel_id) or []}
    if char.startswith("near:"):   # фильтры «что рядом» считает features/nearby одним шагом по карте
        v = f["value"]
        note = (f"На карте в {v['within_min']} мин пешком не нашли" if v.get("meters") is None
                else f"На карте: {v['kind'].lower()} в {v['meters']} м, {v['walk_min']} мин пешком")
        return {"fact": fact_id, "spec": char[5:], "trace": [{"tool": "poi_nearby", "title": "Карта города",
                                                              "status": "found", "note": note,
                                                              "confidence": f["confidence"]}]}
    s = store.get_spec(OWNER.get(char, ""))
    if s is None:
        return {"fact": fact_id, "spec": None, "trace": []}
    return {"fact": fact_id, "spec": s["id"], "trace": research(h, s)["trace"]}
