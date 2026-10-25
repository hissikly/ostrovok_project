from fastapi import APIRouter, HTTPException, Query

from core.seed import load

router = APIRouter(prefix="/api", tags=["okno"])


@router.get("/hotels/{hotel_id}/window")
def window(hotel_id: str, facade: str | None = Query(None, pattern="^[NESW]$"), floor: int | None = None):
    """Вид из окна. Без параметров — какие фасады и этажи посчитаны.
    С facade и floor — доля моря и закат именно этого этажа; лучи для карты — с ближайшего этажа,
    для которого хранится профиль (profile_floor)."""
    d = load(f"okno/{hotel_id}.json")
    if d is None:
        if facade is None:
            return {"hotel_id": hotel_id, "computed": False}
        raise HTTPException(404, detail={"error": "window not computed", "detail": hotel_id})
    if facade is None:
        return {"hotel_id": hotel_id, "computed": True, "confidence": d["confidence"],
                "facades": {s: {"normal_az": f["normal_az"],
                                "floors": {fl: v["sea_share"] for fl, v in f["floors"].items()}}
                            for s, f in d["facades"].items()}}
    f = d["facades"].get(facade)
    if f is None:
        raise HTTPException(404, detail={"error": "facade not computed", "detail": facade})
    floors = sorted(int(k) for k in f["floors"])
    fl = min(floors, key=lambda x: abs(x - (floor or floors[-1])))
    v = f["floors"][str(fl)]
    with_profile = [x for x in floors if "profile" in f["floors"][str(x)]]
    pf = min(with_profile, key=lambda x: abs(x - fl))
    return {"hotel_id": hotel_id, "facade": facade, "floor": fl, "requested_floor": floor,
            "normal_az": f["normal_az"], "eye": f["eye"], "confidence": d["confidence"],
            "eye_m": v["eye_m"], "sea_share": v["sea_share"], "sun": v["sun"],
            "profile_floor": pf, "profile_fields": ["az", "kind", "dist", "sea"],
            "profile": f["floors"][str(pf)]["profile"]}
