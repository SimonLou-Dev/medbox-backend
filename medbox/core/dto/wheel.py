"""DTOs pour les roues et leurs compartiments."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from medbox.core.db.models.wheel import Wheel
from medbox.core.db.models.wheel_slot import WheelSlot


class WheelSlotResponse(BaseModel):
    """Réponse représentant un compartiment de roue."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    wheel_id: UUID
    index: int
    c_label: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, slot: WheelSlot) -> WheelSlotResponse:
        return cls.model_validate(slot)


class WheelSlotUpdateRequest(BaseModel):
    """Mise à jour d'un compartiment de roue."""

    c_label: str | None = None


class WheelRequest(BaseModel):
    """Données pour créer ou mettre à jour une roue."""

    wheel_uid: str
    patient_id: UUID | None = None
    box_id: UUID | None = None
    slot_count: int = 28
    status: str = "prepared"


class WheelResponse(BaseModel):
    """Réponse représentant une roue."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID  # UUID interne, expose pour les actions (mount, load-plan, etc.)
    wheel_uid: str
    tenant_id: UUID | None
    patient_id: UUID | None
    box_id: UUID | None
    slot_count: int
    status: str
    slots: list[WheelSlotResponse] = []
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, wheel: Wheel) -> WheelResponse:
        return cls.model_validate(wheel)


class WheelStatusUpdateRequest(BaseModel):
    """Mise à jour du statut d'une roue."""

    status: str


class WheelStatsResponse(BaseModel):
    """Statistiques agrégées des roues du tenant."""

    total: int
    mounted: int
    prepared: int
    in_stock: int
