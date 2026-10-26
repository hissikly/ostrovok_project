from fastapi import APIRouter, HTTPException

from features.hotels.backend import hotel

from .search import search
from .store import stats, summary

router = APIRouter(prefix="/api", tags=["web_sources"])


def _check(hotel_id: str):
    if hotel(hotel_id) is None:
        raise HTTPException(404, detail={"error": "hotel not found", "detail": hotel_id})


@router.get("/web/stats")
def web_stats():
    return stats()


@router.get("/hotels/{hotel_id}/web")
def hotel_web(hotel_id: str):
    _check(hotel_id)
    return summary(hotel_id)


@router.get("/hotels/{hotel_id}/web/search")
def hotel_web_search(hotel_id: str, q: str, k: int = 4):
    _check(hotel_id)
    return [{key: c[key] for key in ("text", "url", "title", "fetched_at", "score", "matched")}
            for c in search(hotel_id, q, k=min(k, 10))]
