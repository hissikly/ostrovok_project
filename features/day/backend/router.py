from fastapi import APIRouter, HTTPException, Query

from features.day.backend.day import day, route

router = APIRouter(prefix="/api", tags=["day"])


@router.get("/hotels/{hotel_id}/day")
def hotel_day(hotel_id: str, month: int = Query(5, ge=1, le=12), facade: str | None = Query(None, pattern="^[NESW]$"),
              floor: int | None = None, mode: str | None = Query(None, pattern="^kids$"), skip: str = ""):
    """Лента одного дня в месяц поездки для выбранной стороны и этажа (из «О!кна»); skip — места, куда гость не пойдёт."""
    d = day(hotel_id, month, facade, floor, mode, {x for x in skip.split(",") if x})
    if d is None:
        raise HTTPException(404, detail={"error": "hotel not found", "detail": hotel_id})
    return d


@router.get("/hotels/{hotel_id}/day/route")
def hotel_day_route(hotel_id: str, month: int = Query(5, ge=1, le=12), facade: str | None = Query(None, pattern="^[NESW]$"),
                    floor: int | None = None, mode: str | None = Query(None, pattern="^kids$"), skip: str = ""):
    """Выходы из отеля на карту: линии, остановки с номерами, итог; skip — id мест через запятую, которые гость убрал."""
    r = route(hotel_id, month, facade, floor, mode, {x for x in skip.split(",") if x})
    if r is None:
        raise HTTPException(404, detail={"error": "hotel not found", "detail": hotel_id})
    return r
