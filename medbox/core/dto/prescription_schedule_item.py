"""DTOs pour les items de planning de prises."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from medbox.core.db.models.prescription_schedule_item import PrescriptionScheduleItem


class PrescriptionScheduleItemRequest(BaseModel):
    """Données pour créer un item de planning."""

    prescription_id: UUID
    prescription_item_id: UUID | None = None
    box_id: UUID | None = None
    scheduled_at: datetime


class PrescriptionScheduleItemResponse(BaseModel):
    """Réponse représentant un item de planning."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    prescription_id: UUID
    prescription_item_id: UUID | None
    box_id: UUID | None
    scheduled_at: datetime
    status: str
    dispatched_at: datetime | None
    taken_at: datetime | None
    error_reason: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(
        cls,
        item: PrescriptionScheduleItem,
    ) -> PrescriptionScheduleItemResponse:
        return cls.model_validate(item)
