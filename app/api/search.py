from fastapi import APIRouter
from pydantic import BaseModel

from app.services.search import search_meetings


router = APIRouter()


class SearchRequest(BaseModel):
    query: str


@router.post("/search")
async def semantic_search(
    request: SearchRequest
):

    results = search_meetings(
        request.query
    )

    return {
        "query": request.query,
        "results": results
    }