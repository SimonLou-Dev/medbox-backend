"""Routes pour les événements IoT des boxes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from medbox.core.db.repositories.event import EventRepository
from medbox.core.dto.event import EventResponse
from medbox.core.services import CurrentUser, get_user_service
from medbox.core.services.user import UserService

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("/")
async def list_events(
    user: CurrentUser,
    user_svc: Annotated[UserService, Depends(get_user_service)],
    box_id: Annotated[UUID | None, Query()] = None,
    type: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[EventResponse]:
    """Liste les événements IoT du tenant avec filtres optionnels."""
    db_user = await user_svc.get_user_from_subject(user.subject)
    events = await EventRepository().list_by_tenant(
        tenant_id=db_user.tenant_id,
        box_id=box_id,
        event_type=type,
        limit=limit,
    )
    return [EventResponse.from_model(e) for e in events]


@router.get("/alerts")
async def list_alerts(
    user: CurrentUser,
    user_svc: Annotated[UserService, Depends(get_user_service)],
    box_id: Annotated[UUID | None, Query()] = None,
    unacknowledged_only: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[EventResponse]:
    """Liste les alertes du tenant (box_offline, erreurs, maintenance).

    Paramètres optionnels :
    - `box_id` : filtrer par box
    - `unacknowledged_only` : uniquement les alertes non acquittées
    """
    db_user = await user_svc.get_user_from_subject(user.subject)
    alerts = await EventRepository().list_alerts(
        tenant_id=db_user.tenant_id,
        box_id=box_id,
        unacknowledged_only=unacknowledged_only,
        limit=limit,
    )
    return [EventResponse.from_model(a) for a in alerts]


@router.patch("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: UUID,
    user: CurrentUser,
    user_svc: Annotated[UserService, Depends(get_user_service)],
) -> EventResponse:
    """Acquitte une alerte (marque comme traitée)."""
    db_user = await user_svc.get_user_from_subject(user.subject)
    repo = EventRepository()
    event = await repo.acknowledge(alert_id, tenant_id=db_user.tenant_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alerte introuvable",
        )
    return EventResponse.from_model(event)
