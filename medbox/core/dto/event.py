"""DTOs pour les événements."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from medbox.core.db.models.event import Event


class EventResponse(BaseModel):
    """Événement IoT."""

    model_config = ConfigDict(from_attributes=True)

    box_id: UUID | None
    type: str
    payload: dict | None
    created_at: datetime

    @classmethod
    def from_model(cls, e: Event) -> EventResponse:
        return cls.model_validate(e)
