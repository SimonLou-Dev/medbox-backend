"""Routes pour la gestion des boîtiers physiques."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from medbox.core.dto.box import BoxRequest, BoxResponse, BoxStatusUpdateRequest
from medbox.core.services import CurrentUser, get_user_service
from medbox.core.services.box import BoxService
from medbox.core.services.user import UserService

router = APIRouter(prefix="/boxes", tags=["Boxes"])


# ==============================================================================
# Dependency
# ==============================================================================


async def get_box_service(
    user: CurrentUser,
    user_svc: Annotated[UserService, Depends(get_user_service)],
) -> BoxService:
    """Crée un BoxService scoped par le tenant de l'utilisateur."""
    db_user = await user_svc.get_user_from_subject(user.subject)
    return BoxService(tenant_id=db_user.tenant_id)


BoxSvcDep = Annotated[BoxService, Depends(get_box_service)]


# ==============================================================================
# Routes
# ==============================================================================


@router.get("/")
async def list_boxes(
    user: CurrentUser,
    box_svc: BoxSvcDep,
) -> list[BoxResponse]:
    """Liste toutes les boxes du tenant."""
    return await box_svc.list()


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_box(
    body: BoxRequest,
    user: CurrentUser,
    box_svc: BoxSvcDep,
) -> BoxResponse:
    """Enregistre une nouvelle box dans le tenant."""
    return await box_svc.create(body)


@router.get("/{box_id}")
async def get_box(
    box_id: UUID,
    user: CurrentUser,
    box_svc: BoxSvcDep,
) -> BoxResponse:
    """Récupère les détails d'une box."""
    return await box_svc.get(box_id)


@router.patch("/{box_id}")
async def update_box(
    box_id: UUID,
    body: BoxRequest,
    user: CurrentUser,
    box_svc: BoxSvcDep,
) -> BoxResponse:
    """Met à jour une box."""
    return await box_svc.update(box_id, body)


@router.patch("/{box_id}/status")
async def update_box_status(
    box_id: UUID,
    body: BoxStatusUpdateRequest,
    user: CurrentUser,
    box_svc: BoxSvcDep,
) -> BoxResponse:
    """Met à jour uniquement le statut d'une box."""
    return await box_svc.update_status(box_id, body)


@router.delete("/{box_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_box(
    box_id: UUID,
    user: CurrentUser,
    box_svc: BoxSvcDep,
) -> None:
    """Supprime une box."""
    await box_svc.delete(box_id)
