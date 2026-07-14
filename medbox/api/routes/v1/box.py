"""Routes pour la gestion des boîtiers physiques."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from medbox.core.celery_app import celery_app
from medbox.core.dto.box import (
    BoxRequest,
    BoxResponse,
    BoxStatsResponse,
    BoxStatusUpdateRequest,
)
from medbox.core.dto.telemetry import TelemetryResponse
from medbox.core.services import CurrentUser, get_user_service
from medbox.core.services.box import BoxService
from medbox.core.services.box_admin import BoxAdminService
from medbox.core.services.user import UserService

router = APIRouter(prefix="/boxes", tags=["Boxes"])


class BoxPageResponse(BaseModel):
    items: list[BoxResponse]
    total: int
    page: int
    per_page: int


async def get_box_service(
    user: CurrentUser,
    user_svc: Annotated[UserService, Depends(get_user_service)],
) -> BoxService:
    db_user = await user_svc.get_user_from_subject(user.subject)
    return BoxService(tenant_id=db_user.tenant_id)


BoxSvcDep = Annotated[BoxService, Depends(get_box_service)]


@router.get("/stats")
async def get_box_stats(
    user: CurrentUser,
    box_svc: BoxSvcDep,
) -> BoxStatsResponse:
    """Statistiques agrégées des boxes du tenant."""
    return await box_svc.get_stats()


@router.get("/")
async def list_boxes(
    user: CurrentUser,
    box_svc: BoxSvcDep,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> BoxPageResponse:
    """Liste les boxes du tenant avec pagination."""
    total, boxes = await box_svc.list_paginated(page=page, per_page=per_page)
    return BoxPageResponse(
        items=[BoxResponse.from_model(b) for b in boxes],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{box_id}")
async def get_box(
    box_id: UUID,
    user: CurrentUser,
    box_svc: BoxSvcDep,
) -> BoxResponse:
    return await box_svc.get(box_id)


@router.patch("/{box_id}")
async def update_box(
    box_id: UUID,
    body: BoxRequest,
    user: CurrentUser,
    box_svc: BoxSvcDep,
) -> BoxResponse:
    return await box_svc.update(box_id, body)


@router.get("/{box_uid}/telemetry")
async def get_box_telemetry(
    box_uid: str,
    user: CurrentUser,
    box_svc: BoxSvcDep,
    metric: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[TelemetryResponse]:
    """Historique de télémétrie d'une box."""
    entries = await box_svc.get_telemetry(box_uid, metric=metric, limit=limit)
    return [TelemetryResponse.from_model(e) for e in entries]


@router.patch("/{box_id}/status")
async def update_box_status(
    box_id: UUID,
    body: BoxStatusUpdateRequest,
    user: CurrentUser,
    box_svc: BoxSvcDep,
) -> BoxResponse:
    return await box_svc.update_status(box_id, body)


# ==============================================================================
# Adoption QR code
# ==============================================================================


@router.post("/{box_uid}/adopt", status_code=status.HTTP_200_OK)
async def adopt_box(
    box_uid: str,
    user: CurrentUser,
    user_svc: Annotated[UserService, Depends(get_user_service)],
) -> BoxResponse:
    """Appaire une box au tenant via scan QR code."""
    db_user = await user_svc.get_user_from_subject(user.subject)
    return await BoxAdminService().adopt(box_uid=box_uid, tenant_id=db_user.tenant_id)


@router.post("/{box_uid}/test-distribution", status_code=status.HTTP_202_ACCEPTED)
async def test_distribution(
    box_uid: str,
    user: CurrentUser,
    box_svc: BoxSvcDep,
) -> dict:
    """Envoie une commande de test de distribution (7 jours) à la box via MQTT."""
    box = await box_svc.box_repo.get_by_uid(box_uid)
    if not box or box.tenant_id != box_svc.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Box '{box_uid}' introuvable",
        )
    celery_app.send_task(
        "medbox.iotworker.tasks.commands.send_test_distribution",
        args=[box.box_uid, 7],
    )
    return {"status": "queued", "box_uid": box.box_uid, "days": 7}


@router.delete("/{box_id}/unadopt", status_code=status.HTTP_200_OK)
async def unadopt_box(
    box_id: UUID,
    user: CurrentUser,
    user_svc: Annotated[UserService, Depends(get_user_service)],
) -> BoxResponse:
    """Détache une box du tenant."""
    db_user = await user_svc.get_user_from_subject(user.subject)
    return await BoxAdminService().unadopt(box_id=box_id, tenant_id=db_user.tenant_id)
