from fastapi import APIRouter, HTTPException

from features.facts.backend.store import facts_for

router = APIRouter(prefix="/api", tags=["facts"])


@router.get("/hotels/{hotel_id}/facts")
def hotel_facts(hotel_id: str):
    return facts_for(hotel_id)


@router.get("/facts/{fact_id}")
def fact(fact_id: str):
    hotel_id = fact_id.split(":", 1)[0]
    for f in facts_for(hotel_id):
        if f["id"] == fact_id:
            return f
    raise HTTPException(404, detail={"error": "fact not found", "detail": fact_id})
