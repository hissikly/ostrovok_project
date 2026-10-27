from fastapi import APIRouter
from pydantic import BaseModel

from features.trip_plan.backend.fit import fit_all
from features.trip_plan.backend.interests import INTERESTS

router = APIRouter(prefix="/api/trip", tags=["trip_plan"])


class FitIn(BaseModel):
    interests: list[str]


@router.get("/interests")
def interests():
    """Каталог интересов для выбора в плашке поездки."""
    return [{k: i[k] for k in ("id", "title", "icon")} for i in INTERESTS]


@router.post("/fit")
def fit(body: FitIn):
    """Сколько интересов у каждого отеля закрываются пешком: {hotel_id: {good, all, far, unknown, score}}."""
    return fit_all(body.interests)
