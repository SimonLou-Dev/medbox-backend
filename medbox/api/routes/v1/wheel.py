"""Routes pour la gestion des roues et de leurs compartiments."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from medbox.core.dto.wheel import (
    WheelResponse,
    WheelSlotResponse,
    WheelSlotUpdateRequest,
    WheelStatsResponse,
    WheelStatusUpdateRequest,
)
from medbox.core.services import CurrentUser, get_user_service
from medbox.core.services.user import UserService
from medbox.core.services.wheel import WheelService
from medbox.core.services.wheel_admin import WheelAdminService

router = APIRouter(prefix="/wheels", tags=["Wheels"])


class WheelPageResponse(BaseModel):
    items: list[WheelResponse]
    total: int
    page: int
    per_page: int


class MountRequest(BaseModel):
    box_id: UUID


async def get_wheel_service(
    user: CurrentUser,
    user_svc: Annotated[UserService, Depends(get_user_service)],
) -> WheelService:
    db_user = await user_svc.get_user_from_subject(user.subject)
    return WheelService(tenant_id=db_user.tenant_id)


WheelSvcDep = Annotated[WheelService, Depends(get_wheel_service)]


# ==============================================================================
# Roues
# ==============================================================================


@router.get("/stats")
async def get_wheel_stats(
    user: CurrentUser,
    wheel_svc: WheelSvcDep,
) -> WheelStatsResponse:
    """Statistiques agrégées des roues du tenant."""
    return await wheel_svc.get_stats()


@router.get("/")
async def list_wheels(
    user: CurrentUser,
    wheel_svc: WheelSvcDep,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> WheelPageResponse:
    """Liste les wheels du tenant avec pagination."""
    total, wheels = await wheel_svc.list_paginated(page=page, per_page=per_page)
    return WheelPageResponse(
        items=[WheelResponse.from_model(w) for w in wheels],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{wheel_id}")
async def get_wheel(
    wheel_id: UUID,
    user: CurrentUser,
    wheel_svc: WheelSvcDep,
) -> WheelResponse:
    return await wheel_svc.get(wheel_id)


@router.patch("/{wheel_id}/status")
async def update_wheel_status(
    wheel_id: UUID,
    body: WheelStatusUpdateRequest,
    user: CurrentUser,
    wheel_svc: WheelSvcDep,
) -> WheelResponse:
    return await wheel_svc.update_status(wheel_id, body)


# ==============================================================================
# Adoption
# ==============================================================================


@router.post("/{wheel_uid}/adopt", status_code=status.HTTP_200_OK)
async def adopt_wheel(
    wheel_uid: str,
    user: CurrentUser,
    user_svc: Annotated[UserService, Depends(get_user_service)],
) -> WheelResponse:
    """Adopte une wheel (scan QR) → rattache au tenant."""
    db_user = await user_svc.get_user_from_subject(user.subject)
    return await WheelAdminService().adopt(
        wheel_uid=wheel_uid, tenant_id=db_user.tenant_id
    )


@router.delete("/{wheel_id}/unadopt", status_code=status.HTTP_200_OK)
async def unadopt_wheel(
    wheel_id: UUID,
    user: CurrentUser,
    user_svc: Annotated[UserService, Depends(get_user_service)],
) -> WheelResponse:
    """Détache une wheel du tenant."""
    db_user = await user_svc.get_user_from_subject(user.subject)
    return await WheelAdminService().unadopt(
        wheel_id=wheel_id, tenant_id=db_user.tenant_id
    )


# ==============================================================================
# Montage / Démontage
# ==============================================================================


@router.post("/{wheel_id}/mount", status_code=status.HTTP_200_OK)
async def mount_wheel(
    wheel_id: UUID,
    body: MountRequest,
    user: CurrentUser,
    user_svc: Annotated[UserService, Depends(get_user_service)],
) -> WheelResponse:
    """Monte une wheel sur une box du tenant."""
    db_user = await user_svc.get_user_from_subject(user.subject)
    return await WheelAdminService().mount(
        wheel_id=wheel_id,
        box_id=body.box_id,
        tenant_id=db_user.tenant_id,
    )


@router.delete("/{wheel_id}/unmount", status_code=status.HTTP_200_OK)
async def unmount_wheel(
    wheel_id: UUID,
    user: CurrentUser,
    user_svc: Annotated[UserService, Depends(get_user_service)],
) -> WheelResponse:
    """Démonte une wheel de sa box."""
    db_user = await user_svc.get_user_from_subject(user.subject)
    return await WheelAdminService().unmount(
        wheel_id=wheel_id, tenant_id=db_user.tenant_id
    )


# ==============================================================================
# Slots
# ==============================================================================


@router.get("/{wheel_id}/slots")
async def list_slots(
    wheel_id: UUID,
    user: CurrentUser,
    wheel_svc: WheelSvcDep,
) -> list[WheelSlotResponse]:
    return await wheel_svc.list_slots(wheel_id)


@router.get("/{wheel_id}/slots/{slot_id}")
async def get_slot(
    wheel_id: UUID,
    slot_id: UUID,
    user: CurrentUser,
    wheel_svc: WheelSvcDep,
) -> WheelSlotResponse:
    return await wheel_svc.get_slot(wheel_id, slot_id)


@router.patch("/{wheel_id}/slots/{slot_id}")
async def update_slot(
    wheel_id: UUID,
    slot_id: UUID,
    body: WheelSlotUpdateRequest,
    user: CurrentUser,
    wheel_svc: WheelSvcDep,
) -> WheelSlotResponse:
    return await wheel_svc.update_slot(wheel_id, slot_id, body)
