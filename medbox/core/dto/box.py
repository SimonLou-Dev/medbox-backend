"""DTOs pour les boîtiers physiques."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from medbox.core.db.models.box import Box


class BoxRequest(BaseModel):
    """Données pour créer ou mettre à jour une box."""

    box_uid: str
    name: str | None = None
    patient_id: UUID | None = None
    status: str = "active"
    firmware_version: str | None = None
    software_version: str | None = None
    timezone: str | None = None


class BoxResponse(BaseModel):
    """Réponse représentant une box."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    box_uid: str
    name: str | None
    patient_id: UUID | None
    status: str
    firmware_version: str | None
    software_version: str | None
    timezone: str | None
    battery_level: int | None
    on_battery: bool
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, box: Box) -> BoxResponse:
        return cls.model_validate(box)


class BoxStatusUpdateRequest(BaseModel):
    """Mise à jour du statut d'une box."""

    status: str
