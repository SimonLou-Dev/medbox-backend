"""DTO pour les réponses d'erreur standardisées."""

from typing import ClassVar

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Réponse d'erreur standardisée pour toutes les API endpoints.

    Pattern: Toujours utiliser cette structure pour les erreurs HTTP 4xx/5xx.

    Exemples:
        - 400 Bad Request: message='Email already registered'
        - 403 Forbidden: message='Cross-tenant access denied'
        - 404 Not Found: message='Tenant not found'
        - 500 Internal Server Error: message='Database connection failed'

    """

    status: str = Field(
        default="error",
        description="Status: 'error' | 'validation_error'",
    )
    message: str = Field(description="Message d'erreur lisible")
    error_code: str | None = Field(
        default=None,
        description="Code technique pour logs",
    )
    details: dict | None = Field(
        default=None,
        description="Détails additionnels (validation errors, etc)",
    )
    tenant_id: str | None = Field(
        default=None,
        description="Tenant_id du contexte (pour audit logs)",
    )

    model_config: ClassVar = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "error",
                    "message": "Email address already exists in system",
                    "error_code": "USER_EMAIL_DUPLICATE",
                    "details": {"field": "email", "value": "test@example.com"},
                    "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                },
                {
                    "status": "validation_error",
                    "message": "Invalid request body",
                    "error_code": "VALIDATION_FAILED",
                    "details": {
                        "fields": {
                            "email": "Invalid email format",
                            "password": "Must be at least 8 characters",
                        },
                    },
                },
            ],
        },
    }


class SuccessResponse(BaseModel):
    """Réponse de succès standardisée."""

    status: str = Field(default="ok", description="Status: 'ok'")
    data: dict | None = Field(default=None, description="Payload de la réponse")
    message: str | None = Field(default=None, description="Message optionnel")

    model_config: ClassVar = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "ok",
                    "data": {"user_id": "123", "email": "test@example.com"},
                    "message": "User created successfully",
                },
            ],
        },
    }
