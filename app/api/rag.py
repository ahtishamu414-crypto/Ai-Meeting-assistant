from fastapi import APIRouter
from pydantic import BaseModel

from app.services.rag import ask_meeting


router = APIRouter()


# ============================================================
# REQUEST MODEL
# ============================================================

class QuestionRequest(BaseModel):
    question: str
    top_k: int = 3


# ============================================================
# QUESTION ENDPOINT
# ============================================================

@router.post("/question")
async def question(
    request: QuestionRequest
):
    """
    Ask a question about stored meetings.
    """

    return ask_meeting(
        question=request.question,
        top_k=request.top_k
    )