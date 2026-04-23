from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_user
from app.errors import ApiError
from app.schemas import (
    EnvelopeMeta,
    EvaluateStrictRequest,
    EvaluateStrictResponse,
    EvaluationHistoryResponse,
    EvaluationOCRPreviewRequest,
    EvaluationOCRPreviewResponse,
    MCQHistoryResponse,
    PYQImportRequest,
    PYQImportResponse,
    PYQSyncRequest,
    PYQSyncResponse,
    MCQStartRequest,
    MCQStartResponse,
    MCQSubmitRequest,
    MCQSubmitResponse,
)
from app.services.answer_eval_engine import answer_evaluation_engine
from app.services.mcq_engine import mcq_engine
from app.utils.common import new_id


router = APIRouter(tags=["core"])


@router.post("/mcq/start", response_model=MCQStartResponse)
def mcq_start(payload: MCQStartRequest, current_user: dict = Depends(get_current_user)):
    data = mcq_engine.start_test(
        user_id=current_user["id"],
        topic_text=payload.topic_text,
        question_count=payload.question_count,
    )
    return {"ok": True, "data": data, "meta": EnvelopeMeta(request_id=new_id("req"))}


@router.post("/mcq/pyq/import", response_model=PYQImportResponse)
def mcq_import_pyqs(payload: PYQImportRequest, current_user: dict = Depends(get_current_user)):
    _ = current_user
    data = mcq_engine.import_verified_pyqs(
        topic_text=payload.topic_text,
        questions=[item.model_dump() for item in payload.questions],
    )
    return {"ok": True, "data": data, "meta": EnvelopeMeta(request_id=new_id("req"))}


@router.post("/mcq/pyq/sync", response_model=PYQSyncResponse)
def mcq_sync_pyqs(payload: PYQSyncRequest, current_user: dict = Depends(get_current_user)):
    _ = current_user
    if payload.source != "upscpredict":
        raise ApiError(400, "UNSUPPORTED_SOURCE", "Unsupported PYQ sync source.")
    data = mcq_engine.sync_upscpredict_pyqs()
    return {"ok": True, "data": data, "meta": EnvelopeMeta(request_id=new_id("req"))}


@router.post("/mcq/submit", response_model=MCQSubmitResponse)
def mcq_submit(payload: MCQSubmitRequest, current_user: dict = Depends(get_current_user)):
    data = mcq_engine.submit_test(
        user_id=current_user["id"],
        session_id=payload.session_id,
        answers=[item.model_dump() for item in payload.answers],
    )
    return {"ok": True, "data": data, "meta": EnvelopeMeta(request_id=new_id("req"))}


@router.get("/mcq/history", response_model=MCQHistoryResponse)
def mcq_history(limit: int = Query(default=20, ge=1, le=100), current_user: dict = Depends(get_current_user)):
    data = mcq_engine.get_history(user_id=current_user["id"], limit=limit)
    return {"ok": True, "data": data, "meta": EnvelopeMeta(request_id=new_id("req"))}


@router.post("/evaluation/ocr-preview", response_model=EvaluationOCRPreviewResponse)
def evaluation_ocr_preview(payload: EvaluationOCRPreviewRequest, current_user: dict = Depends(get_current_user)):
    _ = current_user
    data = answer_evaluation_engine.preview_ocr(
        student_answer=payload.student_answer,
        ocr_text=payload.ocr_text,
        handwritten_image_base64=payload.handwritten_image_base64,
        handwritten_image_mime_type=payload.handwritten_image_mime_type,
    )
    return {"ok": True, "data": data, "meta": EnvelopeMeta(request_id=new_id("req"))}


@router.post("/evaluation/evaluate", response_model=EvaluateStrictResponse)
def evaluation_evaluate(payload: EvaluateStrictRequest, current_user: dict = Depends(get_current_user)):
    data = answer_evaluation_engine.evaluate(
        user_id=current_user["id"],
        question=payload.question,
        student_answer=payload.student_answer,
        ocr_text=payload.ocr_text,
        handwritten_image_base64=payload.handwritten_image_base64,
        handwritten_image_mime_type=payload.handwritten_image_mime_type,
        concept_universe=payload.concept_universe,
        max_marks=payload.max_marks,
    )
    return {"ok": True, "data": data, "meta": EnvelopeMeta(request_id=new_id("req"))}


@router.get("/evaluation/history", response_model=EvaluationHistoryResponse)
def evaluation_history(limit: int = Query(default=20, ge=1, le=100), current_user: dict = Depends(get_current_user)):
    data = answer_evaluation_engine.get_history(user_id=current_user["id"], limit=limit)
    return {"ok": True, "data": data, "meta": EnvelopeMeta(request_id=new_id("req"))}
