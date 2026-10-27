from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from core.config import SEED
from features.hotels.backend import hotel
from features.sights.backend import nearest, sights

router = APIRouter(prefix="/api", tags=["sights"])
KEYS = ("id", "name", "to", "about", "tags", "duration", "lat", "lon", "walkable", "credit")


@router.get("/sights")
def list_sights():
    """Подборка «Что посмотреть» с фото (data/seed/sights/<id>.jpg) и подписью автора."""
    return [{**{k: s.get(k) for k in KEYS}, "photo": f"/api/sights/{s['id']}/photo.jpg", "lens": f"sight_{s['id']}"}
            for s in sights()]


@router.get("/sights/{sight_id}/photo.jpg")
def photo(sight_id: str):
    path = SEED / "sights" / f"{sight_id}.jpg"
    if not path.exists() or "/" in sight_id or sight_id.startswith("."):
        raise HTTPException(404, detail={"error": "not found", "detail": sight_id})
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})


@router.get("/hotels/{hotel_id}/sights")
def hotel_sights(hotel_id: str, limit: int = 3):
    """Ближайшие к отелю места подборки: пешком по графу или ≈ на машине."""
    h = hotel(hotel_id)
    if h is None:
        raise HTTPException(404, detail={"error": "not found", "detail": hotel_id})
    return nearest(h, limit=min(max(limit, 1), 12))
