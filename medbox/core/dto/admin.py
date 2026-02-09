"""DTOs pour le panneau d'administration."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from medbox.core.constants.enums import UserRoles


# ==============================================================================
# Response DTOs
# ==============================================================================


class MemberResponse(BaseModel):
    """Un membre du tenant."""

    id: UUID
    email: str
    full_name: str | None = None
    role: str
    status: str
    created_at: datetime | None = None


class MemberListResponse(BaseModel):
    """Liste des membres du tenant."""

    members: list[MemberResponse]
    total: int


class TenantStatsResponse(BaseModel):
    """Stats agregees pour le panneau admin."""

    member_count: int = 0
    admin_count: int = 0
    caregiver_count: int = 0
    patient_role_count: int = 0
    default_count: int = 0
    patient_count: int = 0
    box_count: int = 0
    wheel_count: int = 0
    invitation_count: int = 0
    pending_invitation_count: int = 0


class InvitationHistoryItem(BaseModel):
    """Une invitation dans l'historique."""

    id: UUID
    code: str
    status: str
    expires_at: datetime
    created_at: datetime
    sent_by_name: str | None = None
    sent_by_email: str | None = None
    claimed_by_name: str | None = None
    claimed_by_email: str | None = None


class InvitationHistoryResponse(BaseModel):
    """Historique des invitations."""

    invitations: list[InvitationHistoryItem]
    total: int


class ActivityItem(BaseModel):
    """Un element du fil d'activite."""

    type: str
    description: str
    actor_name: str | None = None
    target_name: str | None = None
    timestamp: datetime


class ActivityFeedResponse(BaseModel):
    """Fil d'activite."""

    activities: list[ActivityItem]


# ==============================================================================
# Request DTOs
# ==============================================================================


class UpdateMemberRoleRequest(BaseModel):
    """Requete pour changer le role d'un membre."""

    role: UserRoles
