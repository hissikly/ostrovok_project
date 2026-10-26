from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from features.hotels.backend import hotel

from .feedback import stats
from .service import book, finish, hotel_reply, list_bookings, trip
from .wish import wish

router = APIRouter(prefix="/api", tags=["trip"])


class BookingIn(BaseModel):
    hotel_id: str
    month: int = 5
    facade: str | None = None
    floor: int | None = None
    drop: list[str] = []      # пункты пожелания, которые гость убрал


class FinishIn(BaseModel):
    answers: dict[str, str] = {}   # {id пункта обещания | "wish": "yes" | "no" | "unsure"}


class ReplyIn(BaseModel):
    answer: str               # "confirm" | "decline"
    text: str = ""


def _404(what: str, detail: str):
    raise HTTPException(404, detail={"error": f"{what} not found", "detail": detail})


@router.get("/hotels/{hotel_id}/request")
def booking_request(hotel_id: str, month: int = Query(5, ge=1, le=12), facade: str | None = Query(None, pattern="^[NESW]$"),
                    floor: int | None = None, drop: str = ""):
    """Пожелание к брони из выбранного в «О!кне» и фактов: текст и пункты с причинами."""
    w = wish(hotel_id, month, facade, floor, {x for x in drop.split(",") if x})
    return w if w is not None else _404("hotel", hotel_id)


@router.post("/bookings")
def create_booking(b: BookingIn):
    r = book(b.hotel_id, b.month, b.facade, b.floor, set(b.drop))
    return trip(r["id"]) if r else _404("hotel", b.hotel_id)


@router.get("/bookings")
def bookings(hotel_id: str | None = None):
    return list_bookings(hotel_id)


@router.get("/bookings/{booking_id}")
def get_trip(booking_id: str, kids: bool = False):
    """«Моя поездка»: бронь, пожелание и ответ отеля, обещание с ответами гостей, чемодан."""
    t = trip(booking_id, kids)
    return t if t is not None else _404("booking", booking_id)


@router.post("/bookings/{booking_id}/feedback")
def feedback(booking_id: str, f: FinishIn):
    """«Поездка завершена» и ответы «Так и было?»."""
    if finish(booking_id, f.answers) is None:
        _404("booking", booking_id)
    return trip(booking_id)


@router.get("/feedback/stats")
def feedback_stats():
    """Доля «так и было» по типам фактов (демо-ответы посчитаны отдельно в demo)."""
    return stats()


@router.get("/hotelier/{hotel_id}/bookings")
def hotel_bookings(hotel_id: str):
    """Экстранет: брони с пожеланием."""
    if hotel(hotel_id) is None:
        _404("hotel", hotel_id)
    return list_bookings(hotel_id)


@router.post("/hotelier/{hotel_id}/bookings/{booking_id}")
def reply(hotel_id: str, booking_id: str, r: ReplyIn):
    """Ответ отеля на пожелание: «Подтверждаем» или «Не сможем, предложим…»."""
    if r.answer not in ("confirm", "decline"):
        raise HTTPException(422, detail={"error": "answer must be confirm or decline", "detail": r.answer})
    out = hotel_reply(hotel_id, booking_id, r.answer, r.text)
    return out if out is not None else _404("booking", booking_id)
