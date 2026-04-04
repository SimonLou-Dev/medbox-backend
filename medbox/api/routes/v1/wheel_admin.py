"""Routes d'administration système pour les wheels (super-admin)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from medbox.core.dto.wheel import WheelResponse
from medbox.core.services.tenant_right import require_superadmin
from medbox.core.services.wheel_admin import WheelAdminListResponse, WheelAdminService

router = APIRouter(prefix="/admin/wheels", tags=["Admin — Wheels"])

SuperAdmin = Annotated[object, Depends(require_superadmin())]


class AdminWheelCreateRequest(BaseModel):
    wheel_uid: str
    slot_count: int = 28


@router.get("/")
async def admin_list_wheels(
    _: SuperAdmin,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> WheelAdminListResponse:
    """Liste toutes les wheels avec état d'adoption et box associée."""
    return await WheelAdminService().list_all(page=page, per_page=per_page)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def admin_create_wheel(
    body: AdminWheelCreateRequest,
    _: SuperAdmin,
) -> WheelResponse:
    """Crée une wheel sans tenant. Sera adoptée par un tenant."""
    return await WheelAdminService().create(wheel_uid=body.wheel_uid, slot_count=body.slot_count)


@router.patch("/{wheel_id}/detach")
async def admin_detach_wheel(
    wheel_id: UUID,
    _: SuperAdmin,
) -> WheelResponse:
    """Détache une wheel de sa box (status → in_stock)."""
    return await WheelAdminService().detach(wheel_id=wheel_id)


@router.delete("/{wheel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_wheel(
    wheel_id: UUID,
    _: SuperAdmin,
) -> None:
    """Supprime définitivement une wheel et ses slots."""
    await WheelAdminService().delete(wheel_id=wheel_id)
