from __future__ import annotations

from app.config import settings
from app.database import db
from app.errors import ApiError
from app.security import create_access_token, hash_password, verify_password
from app.utils.common import new_id, utc_now_iso


def _user_public(record: dict) -> dict:
    return {
        "id": record["id"],
        "name": record["name"],
        "email": record["email"],
        "created_at": record["created_at"],
    }


def create_user(name: str, email: str, password: str) -> dict:
    existing = db.fetch_one("SELECT * FROM users WHERE email = ?", [email.lower()])
    if existing:
        raise ApiError(409, "USER_EXISTS", "An account already exists for this email.")

    now = utc_now_iso()
    user = {
        "id": new_id("usr"),
        "name": name.strip(),
        "email": email.lower(),
        "password_hash": hash_password(password),
        "created_at": now,
        "updated_at": now,
    }
    with db.session(write=True) as conn:
        conn.execute(
            """
            INSERT INTO users (id, name, email, password_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [user["id"], user["name"], user["email"], user["password_hash"], user["created_at"], user["updated_at"]],
        )

    return {
        "user": _user_public(user),
        "access_token": create_access_token(user["id"], {"email": user["email"]}),
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_seconds,
    }


def authenticate_user(email: str, password: str) -> dict:
    user = db.fetch_one("SELECT * FROM users WHERE email = ?", [email.lower()])
    if not user or not verify_password(password, user["password_hash"]):
        raise ApiError(401, "INVALID_CREDENTIALS", "Email or password is incorrect.")
    return {
        "user": _user_public(user),
        "access_token": create_access_token(user["id"], {"email": user["email"]}),
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_seconds,
    }


def get_user_by_id(user_id: str) -> dict:
    user = db.fetch_one("SELECT * FROM users WHERE id = ?", [user_id])
    if not user:
        raise ApiError(404, "USER_NOT_FOUND", "User does not exist.")
    return _user_public(user)
