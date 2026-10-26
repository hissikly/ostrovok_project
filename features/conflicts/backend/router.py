from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from features.hotels.backend import hotel
from features.knowledge.backend import hotel_path, resolve, write
from features.knowledge.backend.store import get

from .compare import RULES

router = APIRouter(prefix="/api", tags=["conflicts"])


class Resolve(BaseModel):
    action: str          # adopt — «расчёт верный», explain — «мой ответ верный, вот почему»
    text: str | None = None


def _check(hotel_id: str):
    if hotel(hotel_id) is None:
        raise HTTPException(404, detail={"error": "hotel not found", "detail": hotel_id})


def conflicts(hotel_id: str, month: int | None = None) -> list[dict]:
    out = []
    for tid in RULES:
        a = resolve(hotel_id, tid, {"month": month})
        if a.get("conflict"):
            out.append({"question": a["question"], "icon": a["icon"], **a["conflict"]})
    return out


@router.get("/hotels/{hotel_id}/conflicts")
def hotel_conflicts(hotel_id: str, month: int | None = None):
    _check(hotel_id)
    return conflicts(hotel_id, month)


@router.post("/hotelier/{hotel_id}/conflicts/{topic}")
def resolve_conflict(hotel_id: str, topic: str, r: Resolve):
    """Отель разбирает расхождение: принимает расчёт или объясняет свой ответ."""
    _check(hotel_id)
    path = hotel_path(hotel_id)
    own = get(path, topic)
    c = next((x for x in conflicts(hotel_id) if x["topic"] == topic), None)
    if not own or not c:
        raise HTTPException(404, detail={"error": "conflict not found", "detail": topic})
    ev = {**(own.get("evidence") or {}), "conflict": c}
    if r.action == "adopt":
        return write(path, topic, own["value"], c["computed_text"], "hotelier", 0.95,
                     evidence={**ev, "action": "adopted_computed"})
    if r.action == "explain" and (r.text or "").strip():
        return write(path, topic, own["value"], own["text"], "hotelier", own["confidence"],
                     evidence={**ev, "explanation": r.text.strip()})
    raise HTTPException(400, detail={"error": "bad action", "detail": r.action})
