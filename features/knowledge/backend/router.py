from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from features.hotels.backend import hotel

from .answers import ask, faq, topics

router = APIRouter(prefix="/api", tags=["knowledge"])


class AskIn(BaseModel):
    text: str
    month: int | None = None


def _check(hotel_id: str):
    if hotel(hotel_id) is None:
        raise HTTPException(404, detail={"error": "hotel not found", "detail": hotel_id})


@router.get("/knowledge/topics")
def list_topics():
    return [{k: t[k] for k in ("id", "question", "icon", "fields", "synonyms")} for t in topics()]


@router.get("/hotels/{hotel_id}/faq")
def hotel_faq(hotel_id: str, month: int | None = None):
    _check(hotel_id)
    return faq(hotel_id, {"month": month})


@router.post("/hotels/{hotel_id}/ask")
def hotel_ask(hotel_id: str, q: AskIn):
    _check(hotel_id)
    return ask(hotel_id, q.text, {"month": q.month})
