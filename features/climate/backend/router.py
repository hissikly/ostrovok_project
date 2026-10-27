from fastapi import APIRouter, HTTPException, Query

from core.seed import load

router = APIRouter(prefix="/api", tags=["climate"])


@router.get("/climate/rain")
def rain(month: int = Query(..., ge=1, le=12)):
    """Норма осадков на месяц поездки по сетке над Большим Сочи — для слоя «Осадки» на карте.
    Не прогноз: как обычно бывает в этом месяце (features/climate/pipeline/build_rain.py)."""
    d = load("climate_rain.json")
    if d is None:
        raise HTTPException(404, detail={"error": "no climate data", "detail": "data/seed/climate_rain.json"})
    return {"month": month, "source": d["source"], "years": d["years"], "per": d["per"],
            "grid": d["grid"], "points": d["months"][str(month)]}
