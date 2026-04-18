from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import db
from app.errors import ApiError
from app.routes.auth import router as auth_router
from app.routes.catalog import router as catalog_router
from app.routes.performance import router as performance_router
from app.routes.study import router as study_router
from app.routes.upsc import router as upsc_router
from app.schemas import ErrorPayload
from app.services.calibration_service import calibration_service
from app.services.catalog_service import seed_catalog
from app.services.scheduler_service import scheduler_service
from app.utils.common import new_id


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    calibration_service.bootstrap()
    seed_catalog()
    scheduler_service.start(settings.scheduler_interval_minutes)
    yield
    scheduler_service.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(catalog_router)
app.include_router(performance_router)
app.include_router(study_router)
app.include_router(upsc_router)


def _error_payload(*, code: str, message: str, details: dict | None = None) -> dict:
    details = details or {}
    return ErrorPayload(
        code=code,
        message=message,
        details=details,
        error_type=details.get("error_type"),
        reason=details.get("reason"),
        suggestions=details.get("suggestions", []),
    ).model_dump()


@app.get("/health")
def health():
    return {
        "ok": True,
        "data": {
            "status": "ok",
            "storage_mode": db.storage_mode,
            "ai_mode": "gemini" if settings.gemini_api_key else "demo",
        },
        "meta": {"request_id": new_id("req")},
    }


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, exc: ApiError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "error": _error_payload(code=exc.code, message=exc.message, details=exc.details),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    first_error = exc.errors()[0] if exc.errors() else {}
    message = first_error.get("msg", "Invalid request payload.")
    reason = "invalid_request"
    if "Provide student_answer" in message or "at least 10 characters" in message:
        reason = "empty_or_unreadable"
    elif "Unsupported image MIME type" in message:
        reason = "unsupported_upload_type"
    return JSONResponse(
        status_code=422,
        content={
            "ok": False,
            "error": _error_payload(
                code="REQUEST_INVALID",
                message="We could not validate the submitted input.",
                details={
                    "error_type": "INPUT_INVALID",
                    "reason": reason,
                    "suggestions": [
                        "Write complete sentences",
                        "Avoid empty input",
                        "Retry submission",
                    ],
                    "validation_message": message,
                },
            ),
        },
    )


@app.exception_handler(Exception)
async def generic_error_handler(_: Request, exc: Exception):  # noqa: BLE001
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "error": ErrorPayload(code="INTERNAL_ERROR", message="Unexpected server error.", details={"reason": str(exc)}).model_dump(),
        },
    )
