from fastapi import APIRouter, HTTPException

from features.facts.backend import facts_for
from features.hotels.backend.store import hotel, hotels

router = APIRouter(prefix="/api", tags=["hotels"])


@router.get("/hotels")
def list_hotels():
    """Короткий список для карты: без тяжёлых полей, с числом фактов сверх карточки
    и флагом okno — посчитан ли вид из окна."""
    out = []
    for h in hotels():
        fs = facts_for(h["id"])
        out.append({"id": h["id"], "name": h["name"], "kind_ru": h["kind_ru"], "lat": h["lat"], "lon": h["lon"],
                    "stars": h["stars"], "price_rub": h["mock"]["price_rub"], "facts": len(fs),
                    "okno": any(f["characteristic"] == "sea_view" for f in fs)})
    return out


@router.get("/hotels/{hotel_id}")
def get_hotel(hotel_id: str):
    h = hotel(hotel_id)
    if h is None:
        raise HTTPException(404, detail={"error": "hotel not found", "detail": hotel_id})
    return h
