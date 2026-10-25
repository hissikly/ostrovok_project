from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from features.hotels.backend import hotel

from .questions import ask_hotel, open_questions
from .service import cabinet, confirm, parse_answer, save_answer

router = APIRouter(prefix="/api/hotelier", tags=["hotelier"])


class QuestionIn(BaseModel):
    topic: str | None = None
    text: str = ""


class BulkIn(QuestionIn):
    hotel_ids: list[str]


class AnswerIn(BaseModel):
    question_id: int | None = None
    topic: str | None = None
    text: str = ""
    fields: list[dict] | None = None


class ConfirmIn(BaseModel):
    topic: str
    text: str | None = None


def _check(hotel_id: str):
    if hotel(hotel_id) is None:
        raise HTTPException(404, detail={"error": "hotel not found", "detail": hotel_id})


@router.post("/questions")
def bulk_questions(q: BulkIn):
    """«Спросить у отелей из подборки» в поиске: один вопрос нескольким отелям."""
    if not q.topic and not q.text.strip():
        raise HTTPException(422, detail={"error": "empty question", "detail": None})
    from features.knowledge.backend import resolve
    asked, known = [], 0
    for h in q.hotel_ids[:20]:
        if not hotel(h):
            continue
        if q.topic and resolve(h, q.topic, {}).get("level") == "hotel":   # уже отвечал — не спрашиваем
            known += 1
            continue
        asked.append(ask_hotel(h, q.topic, q.text))
    return {"asked": len(asked), "known": known}


@router.get("/{hotel_id}")
def get_cabinet(hotel_id: str, month: int | None = None):
    _check(hotel_id)
    return cabinet(hotel_id, month)


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


@router.post("/{hotel_id}/parse")
def parse(hotel_id: str, a: AnswerIn):
    """«Как мы поняли»: разбор свободного ответа по полям, ничего не сохраняет."""
    _check(hotel_id)
    from .questions import get_question
    q = get_question(a.question_id) if a.question_id else None
    return parse_answer(q["topic"] if q else a.topic, a.text)


@router.post("/{hotel_id}/answers")
def answer(hotel_id: str, a: AnswerIn):
    _check(hotel_id)
    return save_answer(hotel_id, a.question_id, a.topic, a.text, a.fields)


@router.post("/{hotel_id}/confirm")
def confirm_fact(hotel_id: str, c: ConfirmIn):
    _check(hotel_id)
    return confirm(hotel_id, c.topic, c.text)
