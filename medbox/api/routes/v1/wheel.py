"""Routes pour la gestion des roues et de leurs compartiments."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from medbox.core.dto.wheel import (
    WheelRequest,
    WheelResponse,
    WheelSlotResponse,
    WheelSlotUpdateRequest,
    WheelStatusUpdateRequest,
)
from medbox.core.services import CurrentUser, get_user_service
from medbox.core.services.user import UserService
from medbox.core.services.wheel import WheelService

router = APIRouter(prefix="/wheels", tags=["Wheels"])


# ==============================================================================
# Dependency
# ==============================================================================


async def get_wheel_service(
    user: CurrentUser,
    user_svc: Annotated[UserService, Depends(get_user_service)],
) -> WheelService:
    """Crée un WheelService scoped par le tenant de l'utilisateur."""
    db_user = await user_svc.get_user_from_subject(user.subject)
    return WheelService(tenant_id=db_user.tenant_id)


WheelSvcDep = Annotated[WheelService, Depends(get_wheel_service)]


# ==============================================================================
# Routes Roues
# ==============================================================================


@router.get("/")
async def list_wheels(
    user: CurrentUser,
    wheel_svc: WheelSvcDep,
) -> list[WheelResponse]:
    """Liste toutes les roues du tenant."""
    return await wheel_svc.list()


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_wheel(
    body: WheelRequest,
    user: CurrentUser,
    wheel_svc: WheelSvcDep,
) -> WheelResponse:
    """Crée une nouvelle roue et génère automatiquement ses slots."""
    return await wheel_svc.create(body)


@router.get("/{wheel_id}")
async def get_wheel(
    wheel_id: UUID,
    user: CurrentUser,
    wheel_svc: WheelSvcDep,
) -> WheelResponse:
    """Récupère les détails d'une roue avec ses slots."""
    return await wheel_svc.get(wheel_id)


@router.patch("/{wheel_id}")
async def update_wheel(
    wheel_id: UUID,
    body: WheelRequest,
    user: CurrentUser,
    wheel_svc: WheelSvcDep,
) -> WheelResponse:
    """Met à jour une roue."""
    return await wheel_svc.update(wheel_id, body)


@router.patch("/{wheel_id}/status")
async def update_wheel_status(
    wheel_id: UUID,
    body: WheelStatusUpdateRequest,
    user: CurrentUser,
    wheel_svc: WheelSvcDep,
) -> WheelResponse:
    """Met à jour uniquement le statut d'une roue."""
    return await wheel_svc.update_status(wheel_id, body)


@router.delete("/{wheel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wheel(
    wheel_id: UUID,
    user: CurrentUser,
    wheel_svc: WheelSvcDep,
) -> None:
    """Supprime une roue (et ses slots en cascade)."""
    await wheel_svc.delete(wheel_id)


# ==============================================================================
# Routes Slots
# ==============================================================================


@router.get("/{wheel_id}/slots")
async def list_slots(
    wheel_id: UUID,
    user: CurrentUser,
    wheel_svc: WheelSvcDep,
) -> list[WheelSlotResponse]:
    """Liste tous les compartiments d'une roue."""
    return await wheel_svc.list_slots(wheel_id)


@router.get("/{wheel_id}/slots/{slot_id}")
async def get_slot(
    wheel_id: UUID,
    slot_id: UUID,
    user: CurrentUser,
    wheel_svc: WheelSvcDep,
) -> WheelSlotResponse:
    """Récupère un compartiment spécifique."""
    return await wheel_svc.get_slot(wheel_id, slot_id)


@router.patch("/{wheel_id}/slots/{slot_id}")
async def update_slot(
    wheel_id: UUID,
    slot_id: UUID,
    body: WheelSlotUpdateRequest,
    user: CurrentUser,
    wheel_svc: WheelSvcDep,
) -> WheelSlotResponse:
    """Met à jour le label d'un compartiment."""
    return await wheel_svc.update_slot(wheel_id, slot_id, body)
