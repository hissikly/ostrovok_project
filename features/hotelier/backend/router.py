from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from features.hotels.backend import hotel

from .questions import ask_hotel, open_questions

router = APIRouter(prefix="/api/hotelier", tags=["hotelier"])


class QuestionIn(BaseModel):
    topic: str | None = None
    text: str = ""


def _check(hotel_id: str):
    if hotel(hotel_id) is None:
        raise HTTPException(404, detail={"error": "hotel not found", "detail": hotel_id})


@router.get("/{hotel_id}/questions")
def list_questions(hotel_id: str):
    _check(hotel_id)
    return open_questions(hotel_id)


@router.post("/{hotel_id}/questions")
def create_question(hotel_id: str, q: QuestionIn):
    _check(hotel_id)
    if not q.topic and not q.text.strip():
        raise HTTPException(422, detail={"error": "empty question", "detail": None})
    return ask_hotel(hotel_id, q.topic, q.text)
