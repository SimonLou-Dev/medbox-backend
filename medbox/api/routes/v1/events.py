"""Routes pour les événements IoT des boxes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

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
