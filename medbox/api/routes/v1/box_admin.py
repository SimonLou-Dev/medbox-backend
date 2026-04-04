"""Routes d'administration système pour les boxes (super-admin)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from medbox.core.dto.box import BoxResponse
from medbox.core.dto.wheel import WheelResponse
from medbox.core.services.box_admin import BoxAdminListResponse, BoxAdminService
from medbox.core.services.tenant_right import require_superadmin

router = APIRouter(prefix="/admin/boxes", tags=["Admin — Boxes"])

SuperAdmin = Annotated[object, Depends(require_superadmin())]


class AdminBoxCreateRequest(BaseModel):
    box_uid: str
    name: str | None = None


@router.get("/")
async def admin_list_boxes(
    _: SuperAdmin,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> BoxAdminListResponse:
    """Liste toutes les boxes avec leur état d'adoption et dernière connexion."""
    svc = BoxAdminService()
    return await svc.list_all(page=page, per_page=per_page)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def admin_create_box(
    body: AdminBoxCreateRequest,
    _: SuperAdmin,
) -> BoxResponse:
    """Crée une box sans tenant. Sera adoptée via QR par un tenant."""
    svc = BoxAdminService()
    return await svc.create(box_uid=body.box_uid, name=body.name)


@router.patch("/{box_uid}/wheels/{wheel_id}/detach")
async def admin_detach_wheel(
    box_uid: str,
    wheel_id: UUID,
    _: SuperAdmin,
) -> WheelResponse:
    """Détache une wheel de sa box (status → in_stock)."""
    svc = BoxAdminService()
    return await svc.detach_wheel(box_uid=box_uid, wheel_id=wheel_id)


@router.delete("/{box_uid}/wheels/{wheel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_wheel(
    box_uid: str,
    wheel_id: UUID,
    _: SuperAdmin,
) -> None:
    """Supprime définitivement une wheel et ses slots."""
    svc = BoxAdminService()
    await svc.delete_wheel(box_uid=box_uid, wheel_id=wheel_id)
