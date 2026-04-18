from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from app.errors import ApiError


T = TypeVar("T")


class ErrorHandler:
    def with_retries(
        self,
        operation_name: str,
        action: Callable[[], T],
        retries: int = 2,
        fallback: Callable[[], T] | None = None,
    ) -> T:
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                result = action()
                if result in (None, "", []):
                    raise ValueError(f"{operation_name} returned an empty response.")
                return result
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == retries:
                    if fallback is not None:
                        return fallback()
                    raise ApiError(
                        503,
                        "SERVICE_UNAVAILABLE",
                        f"{operation_name} failed.",
                        {"reason": str(last_error)},
                    ) from exc
        if fallback is not None:
            return fallback()
        raise ApiError(503, "SERVICE_UNAVAILABLE", f"{operation_name} failed.", {"reason": str(last_error)})

    @staticmethod
    def fallback_payload(message: str = "Service temporarily unavailable") -> dict[str, str]:
        return {"error": message}


error_handler = ErrorHandler()
