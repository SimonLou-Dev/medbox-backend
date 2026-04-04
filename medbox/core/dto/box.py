"""DTOs pour les boîtiers physiques."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from medbox.core.db.models.box import Box


class BoxRequest(BaseModel):
    """Données pour créer ou mettre à jour une box."""

    box_uid: str
    name: str | None = None
    patient_id: UUID | None = None
    status: str = "active"
    firmware_version: str | None = None
    timezone: str | None = None


class BoxResponse(BaseModel):
    """Réponse représentant une box."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(exclude=True)  # interne uniquement, non exposé en JSON
    box_uid: str
    tenant_id: UUID | None
    name: str | None
    patient_id: UUID | None
    status: str
    firmware_version: str | None
    timezone: str | None
    last_seen_at: datetime | None
    last_sync_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, box: Box) -> BoxResponse:
        return cls.model_validate(box)


class BoxStatusUpdateRequest(BaseModel):
    """Mise à jour du statut d'une box."""

    status: str


class BoxStatsResponse(BaseModel):
    """Statistiques agrégées des boxes du tenant."""

    total: int
    online: int          # last_seen_at < 10min
    offline_alert: int   # actives mais non vues depuis > 10min
    never_connected: int # jamais vues (last_seen_at is null) et actives
