from fastapi import APIRouter
from pydantic import BaseModel

from app.services.rag import ask_meeting


router = APIRouter()


class QuestionRequest(BaseModel):
    question: str


@router.post("/ask")
async def ask_question(
    request: QuestionRequest
):

    return ask_meeting(
        request.question
    )