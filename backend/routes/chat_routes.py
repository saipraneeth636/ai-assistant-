"""Chat API route."""

import logging
# pyrefly: ignore[missing-import]
from fastapi import APIRouter, HTTPException

from ai_assistant import answer_question
from models import ChatRequest, ChatResponse, SuggestionsResponse

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger(__name__)

SUGGESTED_QUESTIONS = [
    "What is the total revenue?",
    "Which product generated the highest revenue?",
    "What is the monthly revenue trend?",
    "Which region generated the highest revenue?",
    "How did revenue change between January and February 2026?",
]


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if not request.question.strip():
        raise HTTPException(status_code=422, detail="Question cannot be empty.")
    try:
        result = answer_question(request.question.strip())
        return result
    except Exception as e:
        logger.error("Chat endpoint error: %s", e)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


@router.get("/suggestions", response_model=SuggestionsResponse)
def suggestions():
    return {"suggestions": SUGGESTED_QUESTIONS}
