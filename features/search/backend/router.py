from fastapi import APIRouter
from pydantic import BaseModel

from .describe import describe
from .lenses import LENSES
from .ranking import search

router = APIRouter(prefix="/api", tags=["search"])


class SearchIn(BaseModel):
    lenses: list[str] = []
    month: int | None = None


class DescribeIn(BaseModel):
    text: str


@router.get("/lenses")
def list_lenses():
    return [{k: l[k] for k in ("id", "title", "icon", "hint")} for l in LENSES]


@router.post("/search")
def do_search(q: SearchIn):
    return search(q.lenses, {"month": q.month})


@router.post("/describe")
def do_describe(q: DescribeIn):
    return describe(q.text)
