"""DTOs pour la gestion des invitations."""

from pydantic import BaseModel

# ==============================================================================
# Response DTOs
# ==============================================================================


class ResponseInvitationDTO(BaseModel):
    """Corp de la requête pour claim une invitation."""

    code: str

    # @classmethod
    # def from_model(cls, m):
    #     # Conversion FORTEMENT typée
    #     return cls(
    #         id=m.id,
    #         email=m.email,
    #         sent_at=m.sent_at.isoformat() if m.sent_at else None,
    #         status=m.status,
    #     )


class ResponseInvitationWithCodeDTO(BaseModel):
    """Corp de la requête pour claim une invitation."""

    code: str


# ==============================================================================
# Request DTOs
# ==============================================================================
class ClaimInvitationDTO(BaseModel):
    """Corp de la requête pour claim une invitation."""

    code: str
