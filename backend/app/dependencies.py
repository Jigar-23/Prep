from __future__ import annotations

from fastapi import Header

from app.errors import ApiError
from app.security import decode_token
from app.services.auth_service import get_user_by_id


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError(401, "UNAUTHORIZED", "Authorization header is missing.")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    return get_user_by_id(payload["sub"])
