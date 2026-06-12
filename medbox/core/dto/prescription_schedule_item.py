"""DTOs pour les items de planning de prises."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from medbox.core.db.models.prescription_schedule_item import PrescriptionScheduleItem


class PrescriptionScheduleItemResponse(BaseModel):
    """Réponse représentant une distribution planifiée."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    wheel_load_plan_id: UUID | None
    wheel_slot_id: UUID | None
    box_id: UUID | None
    scheduled_at: datetime
    status: str
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
