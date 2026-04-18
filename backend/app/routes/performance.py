from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.errors import ApiError
from app.schemas import EnvelopeMeta, PerformanceResponse
from app.services.performance_service import get_performance_snapshot
from app.utils.common import new_id


router = APIRouter(prefix="/performance", tags=["performance"])


@router.get("/{user_id}", response_model=PerformanceResponse)
def performance(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise ApiError(403, "FORBIDDEN", "You can only access your own performance dashboard.")
    return {"ok": True, "data": get_performance_snapshot(user_id), "meta": EnvelopeMeta(request_id=new_id("req"))}
