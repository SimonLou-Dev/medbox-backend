"""DTOs pour la gestion des invitations."""

from datetime import datetime

from pydantic import BaseModel

# ==============================================================================
# Response DTOs
# ==============================================================================


class ResponseInvitationWithCodeDTO(BaseModel):
    """DTO de réponse contenant le code d'invitation et sa date d'expiration."""

    code: str
    expires_at: datetime


# ==============================================================================
# Request DTOs
# ==============================================================================
class ClaimInvitationDTO(BaseModel):
    """Corp de la requête pour claim une invitation."""

    code: str
