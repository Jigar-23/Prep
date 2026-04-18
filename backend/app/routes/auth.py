from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.schemas import AuthRequest, AuthResponse, EnvelopeMeta, UserPublic
from app.schemas import SignupRequest
from app.services.auth_service import authenticate_user, create_user
from app.utils.common import new_id


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse)
def signup(payload: SignupRequest):
    return {"ok": True, "data": create_user(payload.name, payload.email, payload.password), "meta": EnvelopeMeta(request_id=new_id("req"))}


@router.post("/login", response_model=AuthResponse)
def login(payload: AuthRequest):
    return {"ok": True, "data": authenticate_user(payload.email, payload.password), "meta": EnvelopeMeta(request_id=new_id("req"))}


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return {"ok": True, "data": current_user, "meta": {"request_id": new_id("req")}}
