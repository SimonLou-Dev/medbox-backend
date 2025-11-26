"""DTOs pour l'authentification et la gestion des utilisateurs."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

# ==============================================================================
# Response DTOs
# ==============================================================================


class TokenResponse(BaseModel):
    """Réponse contenant les tokens OAuth2."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str | None = Field(None, description="Refresh token")
    token_type: str = Field(default="Bearer", description="Type de token")
    expires_in: int | None = Field(None, description="Durée de validité en secondes")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            ],
        },
    }


class MeResponse(BaseModel):
    """Informations de l'utilisateur connecté."""

    subject: str = Field(..., description="Subject (ID Keycloak)")
    username: str = Field(..., description="Nom d'utilisateur")
    email: EmailStr | None = Field(None, description="Adresse email")
    full_name: str = Field(..., description="Nom complet")
    realm_roles: list[str] = Field(
        default_factory=list,
        description="Rôles de l'utilisateur depuis keycloak",
    )
    role: str = Field(None, description="Rôles de l'utilisateur")
    tenant_id: UUID | None = Field(None, description="ID du tenant")
    status: str = Field(default="active", description="Statut du compte")
    created_at: datetime | None = Field(None, description="Date de création")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "subject": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                    "username": "john.doe",
                    "email": "john.doe@example.com",
                    "full_name": "John DOE",
                    "roles": ["user", "admin"],
                    "tenant_id": 1,
                    "status": "active",
                    "created_at": "2024-01-15T10:30:00Z",
                },
            ],
        },
    }


# ==============================================================================
# Request DTOs
# ==============================================================================


class RefreshTokenRequest(BaseModel):
    """Requête de rafraîchissement de token."""

    refresh_token: str = Field(..., description="Refresh token à utiliser")
