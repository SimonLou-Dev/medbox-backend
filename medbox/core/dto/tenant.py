"""DTOs pour l'authentification et la gestion des tenants."""

# ==============================================================================
# Response DTOs
# ==============================================================================

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TenantResponse(BaseModel):
    """Réponse pour un tenant."""

    id: UUID = Field(None, description="Identifiant du tenant")
    name: str = Field(..., description="Nom du tenant")
    patient_count: int = Field(None, description="Nombre de patient")
    caregiver_count: int = Field(None, description="Nombre de soignant")
    box_count: int = Field(None, description="Nombre de medbox")
    wheel_count: int = Field(None, description="Nombre de roues")
    created_at: datetime | None = Field(None, description="Date de création")


# ==============================================================================
# Request DTOs
# ==============================================================================


class TenantRequest(BaseModel):
    """Corp de la requête pour la création / modification d'un tenant."""

    name: str = Field(..., description="Nom du tenant")
