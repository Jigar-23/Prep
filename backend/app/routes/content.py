from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.schemas import (
    EnvelopeMeta,
    EvaluateRequest,
    EvaluateResponse,
    NotesResponse,
    QuestionSyncRequest,
    QuestionsResponse,
    SyncRequest,
)
from app.services.content_service import get_note_response, get_question_response
from app.services.evaluation_service import evaluate_submission
from app.utils.common import new_id


router = APIRouter(tags=["content"])


@router.post("/notes/get", response_model=NotesResponse)
def get_notes(payload: SyncRequest, current_user: dict = Depends(get_current_user)):
    _ = current_user
    data = get_note_response(payload.exam_id, payload.subject_id, payload.topic_id, payload.client_version, payload.client_content_hash)
    return {"ok": True, "data": data, "meta": EnvelopeMeta(request_id=new_id("req"))}


@router.post("/questions/get", response_model=QuestionsResponse)
def get_questions(payload: QuestionSyncRequest, current_user: dict = Depends(get_current_user)):
    _ = current_user
    data = get_question_response(
        payload.exam_id,
        payload.subject_id,
        payload.topic_id,
        payload.include_types,
        payload.client_version,
        payload.client_content_hash,
    )
    return {"ok": True, "data": data, "meta": EnvelopeMeta(request_id=new_id("req"))}


@router.post("/evaluate", response_model=EvaluateResponse)
def evaluate(payload: EvaluateRequest, current_user: dict = Depends(get_current_user)):
    data = evaluate_submission(current_user["id"], payload.model_dump())
    return {"ok": True, "data": data, "meta": EnvelopeMeta(request_id=new_id("req"))}
