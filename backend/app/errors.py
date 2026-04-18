from __future__ import annotations

from typing import Any


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def input_invalid_error(
    *,
    reason: str,
    message: str = "We could not process the submitted answer.",
    suggestions: list[str] | None = None,
    code: str = "INVALID_ANSWER",
) -> ApiError:
    return ApiError(
        400,
        code,
        message,
        {
            "error_type": "INPUT_INVALID",
            "reason": reason,
            "suggestions": suggestions
            or [
                "Write complete sentences",
                "Avoid empty input",
                "Retry submission",
            ],
        },
    )
