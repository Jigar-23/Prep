from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_user
from app.schemas import (
    DailyQuestionResponse,
    EnvelopeMeta,
    EvaluateUPSCRequest,
    EvaluateUPSCResponse,
    FlashcardsResponse,
    GenerateFlashcardsRequest,
    GenerateNotesRequest,
    NotesResponse,
    ReviewCardsResponse,
    UpdateProgressRequest,
    UpdateProgressResponse,
)
from app.services.continuity_service import get_daily_question
from app.services.evaluation_engine import evaluation_engine
from app.services.flashcard_engine import flashcard_engine
from app.services.notes_engine import notes_engine
from app.services.revision_engine import revision_engine
from app.utils.common import new_id


router = APIRouter(tags=["upsc"])


@router.post("/evaluate", response_model=EvaluateUPSCResponse)
def evaluate(payload: EvaluateUPSCRequest, current_user: dict = Depends(get_current_user)):
    data = evaluation_engine.evaluate(user_id=current_user["id"], payload=payload.model_dump())
    return {"ok": True, "data": data, "meta": EnvelopeMeta(request_id=new_id("req"))}


@router.get("/daily-question", response_model=DailyQuestionResponse)
def daily_question(exam_id: str | None = Query(default=None), current_user: dict = Depends(get_current_user)):
    data = {"daily_question": get_daily_question(current_user["id"], exam_id)}
    return {"ok": True, "data": data, "meta": EnvelopeMeta(request_id=new_id("req"))}


@router.post("/generate-notes", response_model=NotesResponse)
def generate_notes(payload: GenerateNotesRequest, current_user: dict = Depends(get_current_user)):
    _ = current_user
    notes = notes_engine.get_or_generate_notes(payload.topic_id)
    return {"ok": True, "data": {"notes": notes}, "meta": EnvelopeMeta(request_id=new_id("req"))}


@router.post("/generate-flashcards", response_model=FlashcardsResponse)
def generate_flashcards(payload: GenerateFlashcardsRequest, current_user: dict = Depends(get_current_user)):
    flashcards, revision = flashcard_engine.get_or_generate_flashcards(topic_id=payload.topic_id, user_id=current_user["id"])
    return {"ok": True, "data": {"flashcards": flashcards, "revision": revision}, "meta": EnvelopeMeta(request_id=new_id("req"))}


@router.get("/review-cards", response_model=ReviewCardsResponse)
def review_cards(limit: int = Query(default=20, ge=1, le=100), current_user: dict = Depends(get_current_user)):
    data = revision_engine.get_due_cards(user_id=current_user["id"], limit=limit)
    return {"ok": True, "data": data, "meta": EnvelopeMeta(request_id=new_id("req"))}


@router.post("/update-progress", response_model=UpdateProgressResponse)
def update_progress(payload: UpdateProgressRequest, current_user: dict = Depends(get_current_user)):
    data = revision_engine.update_progress(user_id=current_user["id"], card_id=payload.card_id, correct=payload.correct)
    return {"ok": True, "data": data, "meta": EnvelopeMeta(request_id=new_id("req"))}
