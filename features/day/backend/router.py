from fastapi import APIRouter, HTTPException, Query

from features.day.backend.day import day, route

router = APIRouter(prefix="/api", tags=["day"])


def _trip(interests, pins):
    """interests=sea,culture → кортеж; pins=culture:node/1,party:node/2 → {интерес: место}."""
    ii = tuple(x for x in interests.split(",") if x)
    pp = dict(x.split(":", 1) for x in pins.split(",") if ":" in x)
    return ii, pp


@router.get("/hotels/{hotel_id}/day")
def hotel_day(hotel_id: str, month: int = Query(5, ge=1, le=12), facade: str | None = Query(None, pattern="^[NESW]$"),
              floor: int | None = None, mode: str | None = Query(None, pattern="^kids$"), skip: str = "",
              interests: str = "", variant: int = Query(0, ge=0), pins: str = ""):
    """Лента одного дня в месяц поездки для выбранной стороны и этажа (из «О!кна»); skip — места, куда гость не пойдёт.
    interests — день по интересам (features/trip_plan): variant — номер варианта, pins — закреплённые места."""
    ii, pp = _trip(interests, pins)
    d = day(hotel_id, month, facade, floor, mode, {x for x in skip.split(",") if x}, ii, variant, pp)
    if d is None:
        raise HTTPException(404, detail={"error": "hotel not found", "detail": hotel_id})
    return d


@router.get("/hotels/{hotel_id}/day/route")
def hotel_day_route(hotel_id: str, month: int = Query(5, ge=1, le=12), facade: str | None = Query(None, pattern="^[NESW]$"),
                    floor: int | None = None, mode: str | None = Query(None, pattern="^kids$"), skip: str = "",
                    interests: str = "", variant: int = Query(0, ge=0), pins: str = ""):
    """Выходы из отеля на карту: линии, остановки с номерами, итог; skip — id мест через запятую, которые гость убрал."""
    ii, pp = _trip(interests, pins)
    r = route(hotel_id, month, facade, floor, mode, {x for x in skip.split(",") if x}, ii, variant, pp)
    if r is None:
        raise HTTPException(404, detail={"error": "hotel not found", "detail": hotel_id})
    return r
