"""DTOs for patient prescription."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from medbox.core.dto.global_medication import GlobalMedicationResponse
from medbox.core.dto.patient import PatientResponse


class DoseSchema(BaseModel):
    """Schema representant une dose de médicament."""

    value: float = Field(..., gt=0)
    unit: str = Field(..., min_length=1, max_length=20)


class FrequencySchema(BaseModel):
    """Schema representant une fréquence de prise de médicament."""

    times_per_day: int | None = Field(None, ge=1, le=10)
    moments: list[str] | None = Field(None)  # ["matin", "midi", "soir"]
    pattern: str = Field(..., min_length=1, max_length=128)  # "3x/jour" pour affichage
    notes: str | None = Field(None, max_length=256)


class PrescriptionItemRequest(BaseModel):
    """Request DTO for a prescription item."""

    medication_cis: int | None
    medication_label: str = Field(..., min_length=1, max_length=255)
    dose: DoseSchema | None
    frequency: FrequencySchema
    extra_instructions: str | None = Field(None, max_length=512)


class PrescriptionItemResponse(BaseModel):
    """Response DTO for a prescription item."""

    id: UUID
    medication_cis: int | None
    medication_label: str
    dose: DoseSchema | None
    frequency: FrequencySchema
    extra_instructions: str | None
    medication: GlobalMedicationResponse | None  # si relation chargée
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PrescriptionRequest(BaseModel):
    """Request DTO for creating/updating a prescription."""

    patient_id: UUID
    title: str | None = Field(None, max_length=255)
    c_notes: str | None
    status: str = Field(default="active", pattern="^(active|paused|stopped|expired)$")
    start_date: datetime | None
    end_date: datetime | None
    items: list[PrescriptionItemRequest] = Field(..., min_length=1)


class PrescriptionResponse(BaseModel):
    """Response DTO for a prescription."""

    id: UUID
    tenant_id: UUID
    patient_id: UUID
    created_by_user_id: UUID | None
    title: str | None
    c_notes: str | None
    status: str
    start_date: datetime | None
    end_date: datetime | None
    created_at: datetime
    updated_at: datetime

    # Document metadata
    has_document: bool  # computed: document_s3_key is not None
    document_file_name: str | None
    document_file_size: int | None
    document_mime_type: str | None
    document_uploaded_at: datetime | None

    # Relations
    items: list[PrescriptionItemResponse] = Field(default_factory=list)
    patient: PatientResponse | None = None

    model_config = {"from_attributes": True}

    @field_validator("has_document", mode="before")
    @classmethod
    def compute_has_document(cls, v: Any, info: ValidationInfo) -> bool:
        """Compute has_document from document_s3_key."""
        # If the source object has document_s3_key attribute, use it
        if hasattr(info.data, "document_s3_key"):
            return info.data.document_s3_key is not None
        # Otherwise return the value as-is
        return bool(v) if v is not None else False


class StatusUpdateRequest(BaseModel):
    """Request DTO for updating prescription status only."""

    status: str = Field(
        ...,
        pattern="^(active|paused|stopped|expired)$",
        description="New status",
    )
