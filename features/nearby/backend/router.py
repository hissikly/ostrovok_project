from fastapi import APIRouter, HTTPException

from features.hotels.backend import hotel
from features.nearby.backend.tool import places, specs

router = APIRouter(prefix="/api", tags=["nearby"])


@router.get("/hotels/{hotel_id}/nearby/{spec_id}")
def hotel_places(hotel_id: str, spec_id: str):
    """Все места одного типа рядом с отелем (ближайшие первыми) — для карты."""
    h = hotel(hotel_id)
    spec = next((s for s in specs() if s["id"] == spec_id), None)
    if h is None or spec is None:
        raise HTTPException(404, detail={"error": "not found", "detail": f"{hotel_id}/{spec_id}"})
    return {"spec": spec_id, "title": spec["title"], "kind": spec["kind"], "within_min": spec["partial_min"],
            "items": places(h, spec)}
