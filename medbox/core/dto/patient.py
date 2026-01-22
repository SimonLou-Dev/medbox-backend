"""DTOs for patient management."""

from datetime import date, datetime
from typing import TYPE_CHECKING, ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from medbox.core.dto.pagination import PagedResponse

if TYPE_CHECKING:
    from medbox.core.db.models.patient import Patient

# ==============================================================================
# Response DTOs
# ==============================================================================


class PatientResponse(BaseModel):
    """Response model for a patient."""

    id: UUID = Field(..., description="Patient unique identifier")
    tenant_id: UUID = Field(..., description="Tenant identifier")
    external_id: str | None = Field(
        None,
        description="External identifier (EHR, DPI, etc.)",
    )
    c_first_name: str = Field(..., description="Patient first name (encrypted)")
    c_last_name: str = Field(..., description="Patient last name (encrypted)")
    c_address: str | None = Field(None, description="Patient address (encrypted)")
    c_phone: str | None = Field(
        None,
        description="Patient phone number (encrypted)",
    )
    birth_date: date | None = Field(
        None,
        description="Patient birth date format YYYY-MM-DD",
    )
    created_at: datetime = Field(..., description="Creation date")
    updated_at: datetime = Field(..., description="Last modification date")

    model_config: ClassVar = {"from_attributes": True}

    @classmethod
    def from_model(cls, model: "Patient") -> "PatientResponse":
        """Convert a Patient model to DTO.

        Parameters
        ----------
        model : Patient
            Patient model

        Returns
        -------
        PatientResponse
            Patient DTO

        """
        return cls.model_validate(model)


class PatientListResponse(PagedResponse[PatientResponse]):
    """Paged response for patient list."""


# ==============================================================================
# Request DTOs
# ==============================================================================


class PatientRequest(BaseModel):
    """Request body for patient creation / modification."""

    c_first_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Patient first name",
    )
    c_last_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Patient last name",
    )
    c_address: str | None = Field(
        None,
        max_length=500,
        description="Patient address",
    )
    c_phone: str | None = Field(
        None,
        max_length=20,
        description="Patient phone number",
    )
    birth_date: datetime | None = Field(None, description="Patient birth date")
    external_id: str | None = Field(
        None,
        max_length=255,
        description="External identifier (EHR, DPI)",
    )
