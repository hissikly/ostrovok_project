from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .service import answer, card, profile, save_review, stats

router = APIRouter(prefix="/api", tags=["profile"])


class AnswersIn(BaseModel):
    answers: dict[str, str] = {}   # {id вопроса: "yes" | "no" | "unsure"}; пусто — только «Поездка завершена»


class ReviewIn(BaseModel):
    stars: int = Field(ge=1, le=5)
    text: str = Field("", max_length=2000)


def _404(bid: str):
    raise HTTPException(404, detail={"error": "booking not found", "detail": bid})


@router.get("/profile")
def get_profile():
    """Поездки гостя: предстоящие и прошлые, вопросы «Так и было?» с ответами, отзыв."""
    return profile()


@router.get("/profile/trips/{booking_id}")
def get_trip(booking_id: str):
    return card(booking_id) or _404(booking_id)


@router.post("/profile/trips/{booking_id}/answers")
def post_answers(booking_id: str, a: AnswersIn):
    """«Так и было?» по обещанию, пожеланию и фильтрам поиска."""
    return answer(booking_id, a.answers) or _404(booking_id)


@router.post("/profile/trips/{booking_id}/review")
def post_review(booking_id: str, r: ReviewIn):
    """Мнение об отеле: звёзды и текст своими словами (можно переписать)."""
    return save_review(booking_id, r.stars, r.text) or _404(booking_id)


@router.get("/profile/stats")
def get_stats():
    """Метрика: доля «так и было» по фильтрам, с которыми выбирали отель."""
    return stats()
