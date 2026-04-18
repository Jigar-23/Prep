from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_user
from app.schemas import CatalogResponse, EnvelopeMeta
from app.services.catalog_service import get_catalog_tree
from app.utils.common import new_id


router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/tree", response_model=CatalogResponse)
def catalog_tree(
    exam_id: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
):
    _ = current_user
    return {"ok": True, "data": {"exams": get_catalog_tree(exam_id=exam_id)}, "meta": EnvelopeMeta(request_id=new_id("req"))}
