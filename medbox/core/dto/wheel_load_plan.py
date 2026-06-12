"""DTOs pour les plans de chargement de roue."""

from __future__ import annotations

from datetime import datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WheelLoadPlanCreateRequest(BaseModel):
    """Données pour initier un plan de chargement."""

    wheel_id: UUID
    box_id: UUID
    prescription_ids: list[UUID]
    valid_from: datetime


class WheelLoadPlanConfirmRequest(BaseModel):
    """Confirmation du remplissage physique de la roue par le soignant."""

    box_id: UUID | None = None


class SlotMedicationItem(BaseModel):
    """Un médicament dans une case de la roue."""

    prescription_item_id: UUID
    medication_label: str
    dose: dict | None
    quantity: int


class FillingSlot(BaseModel):
    """Une case de la roue dans la liste de remplissage."""

    slot_index: int
    case_number: int
    scheduled_at: datetime
    distribution_time: time
    day_offset: int
    medications: list[SlotMedicationItem]


class WheelLoadPlanResponse(BaseModel):
    """Réponse représentant un plan de chargement."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    wheel_id: UUID
    box_id: UUID | None
    status: str
    valid_from: datetime | None
    valid_until: datetime | None
    confirmed_at: datetime | None
    total_slots_used: int
    days_covered: int
    created_at: datetime
    updated_at: datetime


class WheelLoadPlanDetailResponse(WheelLoadPlanResponse):
    """Plan de chargement avec la liste complète de remplissage."""

    filling_list: list[FillingSlot]
