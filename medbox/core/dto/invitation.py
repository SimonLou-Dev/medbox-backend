"""DTOs pour la gestion des invitations."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from medbox.core.constants.enums import InviteStatus

# ==============================================================================
# Response DTOs
# ==============================================================================


class ResponseInvitationDTO(BaseModel):
    """DTO de réponse pour une invitation."""

    id: UUID
    email: str
    status: InviteStatus
    expires_at: datetime
    created_at: datetime

    @classmethod
    def from_model(cls, m):
        """Convertit un modèle Invitation en DTO."""
        return cls(
            id=m.id,
            email=m.email,
            status=m.status,
            expires_at=m.expires_at,
            created_at=m.created_at,
        )


class ResponseInvitationWithCodeDTO(BaseModel):
    """Corp de la requête pour claim une invitation."""

    code: str


# ==============================================================================
# Request DTOs
# ==============================================================================
class ClaimInvitationDTO(BaseModel):
    """Corp de la requête pour claim une invitation."""

    code: str
