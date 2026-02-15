"""Service pour le panneau d'administration du tenant."""

from uuid import UUID

from fastapi import HTTPException

from medbox.core.constants.enums import UserRoles, UserStatus
from medbox.core.db.repositories.invitation import InvitationRepository
from medbox.core.db.repositories.tenant import TenantRepository
from medbox.core.db.repositories.user import UserRepository
from medbox.core.dto.admin import (
    ActivityFeedResponse,
    ActivityItem,
    InvitationHistoryItem,
    InvitationHistoryResponse,
    MemberListResponse,
    MemberResponse,
    TenantStatsResponse,
)


class AdminService:
    """Service pour les fonctionnalites d'administration du tenant."""

    def __init__(
        self,
        user_repo: UserRepository,
        tenant_repo: TenantRepository,
        invite_repo: InvitationRepository,
    ) -> None:
        """Constructeur."""
        self.user_repo = user_repo
        self.tenant_repo = tenant_repo
        self.invite_repo = invite_repo

    async def get_stats(self, tenant_id: UUID) -> TenantStatsResponse:
        """Stats agregees pour le panneau admin."""
        user_counts = await self.user_repo.count_by_tenant_and_role(tenant_id)
        invite_counts = await self.invite_repo.count_by_tenant(tenant_id)
        tenant_resp = await self.tenant_repo.get_with_counts(tenant_id)

        return TenantStatsResponse(
            member_count=user_counts["total"],
            admin_count=user_counts["admin_count"],
            caregiver_count=user_counts["caregiver_count"],
            patient_role_count=user_counts["patient_role_count"],
            default_count=user_counts["default_count"],
            patient_count=tenant_resp.patient_count if tenant_resp else 0,
            box_count=tenant_resp.box_count if tenant_resp else 0,
            wheel_count=tenant_resp.wheel_count if tenant_resp else 0,
            invitation_count=invite_counts["total"],
            pending_invitation_count=invite_counts["pending"],
        )

    async def list_members(self, tenant_id: UUID) -> MemberListResponse:
        """List tous les membres du tenant."""
        users = await self.user_repo.list_by_tenant(tenant_id)
        members = [
            MemberResponse(
                id=u.id,
                email=u.email,
                full_name=u.c_full_name,
                role=u.role.value,
                status=u.status.value,
                created_at=u.created_at,
            )
            for u in users
        ]
        return MemberListResponse(members=members, total=len(members))

    async def update_member_role(
        self,
        tenant_id: UUID,
        member_id: UUID,
        new_role: UserRoles,
        admin_user_id: UUID,
    ) -> MemberResponse:
        """Change le role d'un membre."""
        if member_id == admin_user_id:
            raise HTTPException(400, "Vous ne pouvez pas modifier votre propre role")

        user = await self.user_repo.get(member_id)
        if not user or user.tenant_id != tenant_id:
            raise HTTPException(404, "Membre introuvable dans ce tenant")

        if user.role == UserRoles.TENANT_ADMIN:
            raise HTTPException(
                400,
                "Impossible de modifier le role d'un administrateur",
            )

        if new_role == UserRoles.TENANT_ADMIN:
            raise HTTPException(400, "Impossible de promouvoir en administrateur")

        updated = await self.user_repo.update(member_id, {"role": new_role})
        return MemberResponse(
            id=updated.id,
            email=updated.email,
            full_name=updated.c_full_name,
            role=updated.role.value,
            status=updated.status.value,
            created_at=updated.created_at,
        )

    async def remove_member(
        self,
        tenant_id: UUID,
        member_id: UUID,
        admin_user_id: UUID,
    ) -> None:
        """Retire un membre du tenant."""
        if member_id == admin_user_id:
            raise HTTPException(400, "Vous ne pouvez pas vous retirer vous-meme")

        user = await self.user_repo.get(member_id)
        if not user or user.tenant_id != tenant_id:
            raise HTTPException(404, "Membre introuvable dans ce tenant")

        if user.role == UserRoles.TENANT_ADMIN:
            raise HTTPException(400, "Impossible de retirer un administrateur")

        await self.user_repo.update(
            member_id,
            {
                "tenant_id": None,
                "role": UserRoles.DEFAULT,
                "status": UserStatus.PENDING,
            },
        )

    async def get_invitation_history(
        self,
        tenant_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> InvitationHistoryResponse:
        """Historique des invitations du tenant."""
        invitations, total = await self.invite_repo.list_by_tenant(
            tenant_id,
            limit=limit,
            offset=offset,
        )
        items = [
            InvitationHistoryItem(
                id=inv.id,
                code=inv.code,
                status=inv.status.value,
                expires_at=inv.expires_at,
                created_at=inv.created_at,
                sent_by_name=inv.sended_by_user.c_full_name
                if inv.sended_by_user
                else None,
                sent_by_email=inv.sended_by_user.email if inv.sended_by_user else None,
                claimed_by_name=inv.claimed_by_user.c_full_name
                if inv.claimed_by_user
                else None,
                claimed_by_email=inv.claimed_by_user.email
                if inv.claimed_by_user
                else None,
            )
            for inv in invitations
        ]
        return InvitationHistoryResponse(invitations=items, total=total)

    async def get_activity_feed(
        self,
        tenant_id: UUID,
        limit: int = 20,
    ) -> ActivityFeedResponse:
        """Fil d'activite base sur les invitations et les membres."""
        activities: list[ActivityItem] = []

        invitations, _ = await self.invite_repo.list_by_tenant(
            tenant_id,
            limit=limit,
            offset=0,
        )
        for inv in invitations:
            activities.append(
                ActivityItem(
                    type="invitation_created",
                    description=f"Code d'invitation {inv.code} genere",
                    actor_name=inv.sended_by_user.c_full_name
                    if inv.sended_by_user
                    else None,
                    timestamp=inv.created_at,
                ),
            )
            if inv.claimed_by_user:
                activities.append(
                    ActivityItem(
                        type="member_joined",
                        description=f"{inv.claimed_by_user.c_full_name or inv.claimed_by_user.email} a rejoint l'etablissement",
                        target_name=inv.claimed_by_user.c_full_name,
                        timestamp=inv.updated_at,
                    ),
                )

        # Deduplication + tri
        seen = set()
        unique = []
        for act in activities:
            key = (act.type, act.description, act.timestamp)
            if key not in seen:
                seen.add(key)
                unique.append(act)

        unique.sort(key=lambda a: a.timestamp, reverse=True)
        return ActivityFeedResponse(activities=unique[:limit])
