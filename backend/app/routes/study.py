from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_user
from app.schemas import (
    EnvelopeMeta,
    OCRPreviewRequest,
    OCRPreviewResponse,
    StudyDashboardResponse,
    StudyMCQAttemptRequest,
    StudyMCQAttemptResponse,
    StudyPracticeResponse,
    StudyRevisionResponse,
    StudySubjectResponse,
    StudyTopicResponse,
    SubtopicNotesResponse,
)
from app.services.study_service import (
    get_dashboard,
    get_practice_page,
    get_revision_page,
    get_subject_page,
    get_topic_page,
    preview_ocr,
    submit_mcq_attempt,
)
from app.services.subtopic_notes_service import subtopic_notes_service
from app.utils.common import new_id


router = APIRouter(prefix="/study", tags=["study"])


@router.get("/dashboard", response_model=StudyDashboardResponse)
def dashboard(exam_id: str | None = Query(default=None), current_user: dict = Depends(get_current_user)):
    data = get_dashboard(user_id=current_user["id"], exam_id=exam_id)
    return {"ok": True, "data": data, "meta": EnvelopeMeta(request_id=new_id("req"))}


@router.get("/subject/{subject_id}", response_model=StudySubjectResponse)
def subject_page(subject_id: str, exam_id: str | None = Query(default=None), current_user: dict = Depends(get_current_user)):
    data = get_subject_page(user_id=current_user["id"], subject_id=subject_id, exam_id=exam_id)
    return {"ok": True, "data": data, "meta": EnvelopeMeta(request_id=new_id("req"))}


@router.get("/topic/{topic_id}", response_model=StudyTopicResponse)
def topic_page(topic_id: str, current_user: dict = Depends(get_current_user)):
    data = get_topic_page(user_id=current_user["id"], topic_id=topic_id)
    return {"ok": True, "data": data, "meta": EnvelopeMeta(request_id=new_id("req"))}


@router.get("/subtopic/{subtopic_id}/notes", response_model=SubtopicNotesResponse)
def subtopic_notes(subtopic_id: str, current_user: dict = Depends(get_current_user)):
    _ = current_user
    data = subtopic_notes_service.ensure_notes(subtopic_id=subtopic_id)
    return {"ok": True, "data": data, "meta": EnvelopeMeta(request_id=new_id("req"))}


@router.get("/practice", response_model=StudyPracticeResponse)
def practice_page(exam_id: str | None = Query(default=None), current_user: dict = Depends(get_current_user)):
    data = get_practice_page(user_id=current_user["id"], exam_id=exam_id)
    return {"ok": True, "data": data, "meta": EnvelopeMeta(request_id=new_id("req"))}


@router.get("/revision", response_model=StudyRevisionResponse)
def revision_page(exam_id: str | None = Query(default=None), current_user: dict = Depends(get_current_user)):
    data = get_revision_page(user_id=current_user["id"], exam_id=exam_id)
    return {"ok": True, "data": data, "meta": EnvelopeMeta(request_id=new_id("req"))}


@router.post("/ocr-preview", response_model=OCRPreviewResponse)
def ocr_preview(payload: OCRPreviewRequest, current_user: dict = Depends(get_current_user)):
    _ = current_user
    data = preview_ocr(
        answer_text=payload.answer_text,
        handwritten_image_base64=payload.handwritten_image_base64,
        handwritten_image_mime_type=payload.handwritten_image_mime_type,
    )
    return {"ok": True, "data": data, "meta": EnvelopeMeta(request_id=new_id("req"))}


@router.post("/mcq-attempt", response_model=StudyMCQAttemptResponse)
def mcq_attempt(payload: StudyMCQAttemptRequest, current_user: dict = Depends(get_current_user)):
    data = submit_mcq_attempt(user_id=current_user["id"], payload=payload.model_dump())
    return {"ok": True, "data": data, "meta": EnvelopeMeta(request_id=new_id("req"))}
