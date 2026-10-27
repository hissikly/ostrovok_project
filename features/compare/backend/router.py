from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from features.hotels.backend import hotel

from .baseline import baseline
from .compare import compare

router = APIRouter(prefix="/api", tags=["compare"])


class CompareIn(BaseModel):
    ids: list[str]
    lenses: list[str] = []
    month: int | None = None


class BaselineIn(BaseModel):
    lenses: list[str] = []
    month: int | None = None


@router.post("/compare")
def do_compare(q: CompareIn):
    ids = list(dict.fromkeys(q.ids))
    if not 2 <= len(ids) <= 4:
        raise HTTPException(422, detail={"error": "compare 2–4 hotels", "detail": len(ids)})
    missing = [i for i in ids if hotel(i) is None]
    if missing:
        raise HTTPException(404, detail={"error": "hotel not found", "detail": missing})
    return compare(ids, q.lenses, {"month": q.month})


@router.post("/compare/baseline")
def do_baseline(q: BaselineIn):
    return baseline(q.lenses, {"month": q.month})
