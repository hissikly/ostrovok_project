from fastapi import APIRouter
from pydantic import BaseModel, Field

from .describe import describe
from .lenses import LENSES
from .ranking import search

router = APIRouter(prefix="/api", tags=["search"])


class SearchIn(BaseModel):
    lenses: list[str] = []
    month: int | None = None


class DescribeIn(BaseModel):
    text: str = Field(max_length=1000)   # фраза гостя уходит в LLM: длину ограничиваем


@router.get("/lenses")
def list_lenses():
    keys = ("id", "title", "icon", "hint", "primary", "group", "synonyms")
    return [{k: l[k] for k in keys if k in l} for l in LENSES]


@router.post("/search")
def do_search(q: SearchIn):
    return search(q.lenses, {"month": q.month})


@router.post("/describe")
def do_describe(q: DescribeIn):
    return describe(q.text)
