from fastapi import APIRouter, HTTPException, Query

from core.walk import route, to_beach
from features.hotels.backend import hotel

router = APIRouter(prefix="/api", tags=["routes"])


def _hotel(hotel_id):
    h = hotel(hotel_id)
    if h is None:
        raise HTTPException(404, detail={"error": "hotel not found", "detail": hotel_id})
    return h


@router.get("/hotels/{hotel_id}/beach-route")
def beach_route(hotel_id: str):
    """Пешком до ближайшего выхода к пляжу: линия, минуты туда/обратно, подъём, лестницы, переходы."""
    h = _hotel(hotel_id)
    r = to_beach(h["lat"], h["lon"])
    if r is None:
        raise HTTPException(404, detail={"error": "no route", "detail": hotel_id})
    return r


@router.get("/hotels/{hotel_id}/route")
def route_to(hotel_id: str, lat: float = Query(ge=-90, le=90, allow_inf_nan=False),
             lon: float = Query(ge=-180, le=180, allow_inf_nan=False)):
    """Пешком от отеля до точки (магазин, парк…)."""
    h = _hotel(hotel_id)
    r = route(h["lat"], h["lon"], lat, lon)
    if r is None:
        raise HTTPException(404, detail={"error": "no route", "detail": f"{lat},{lon}"})
    return r
