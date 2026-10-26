"""Точка входа: собирает роутеры фич, отдаёт собранный фронт и /health."""
import logging

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core.config import STATIC
from features.beach_route.backend.router import router as routes_router
from features.characteristics.backend.router import router as characteristics_router
from features.conflicts.backend.router import router as conflicts_router
from features.day.backend.router import router as day_router
from features.facts.backend.router import router as facts_router
from features.hotelier.backend.router import router as hotelier_router
from features.hotels.backend.router import router as hotels_router
from features.knowledge.backend.router import router as knowledge_router
from features.okno.backend.router import router as okno_router
from features.nearby.backend.router import router as nearby_router
from features.search.backend.router import router as search_router
from features.trip_plan.backend.router import router as trip_router
from features.web_sources.backend.router import router as web_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = FastAPI(title="О!кно", version="0.1.0")

for r in (hotels_router, facts_router, okno_router, search_router, nearby_router, routes_router, knowledge_router, hotelier_router, conflicts_router,
          day_router, web_router, characteristics_router, trip_router):
    app.include_router(r)


@app.get("/health")
def health():
    return {"status": "ok"}


if (STATIC / "assets").exists():
    app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    index = STATIC / "index.html"
    if not index.exists():
        return {"status": "frontend not built", "hint": "npm run build"}
    return FileResponse(index)
