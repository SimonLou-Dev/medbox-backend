"""Tests d'intégration pour AdminService."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from medbox.core.constants.enums import InviteStatus, UserRoles, UserStatus
from medbox.core.db.models.invitation import Invitation
from medbox.core.db.models.tenant import Tenant
from medbox.core.db.models.user import User
from medbox.core.db.repositories.invitation import InvitationRepository
from medbox.core.db.repositories.tenant import TenantRepository
from medbox.core.db.repositories.user import UserRepository
from medbox.core.services.admin import AdminService

pytestmark = pytest.mark.asyncio


# ==============================================================================
# Helpers
# ==============================================================================


def _make_svc() -> AdminService:
    return AdminService(
        user_repo=UserRepository(),
        tenant_repo=TenantRepository(),
        invite_repo=InvitationRepository(),
    )


async def _create_tenant(db_session: AsyncSession, name: str = "Tenant") -> Tenant:
    tenant = Tenant(id=uuid4(), name=f"{name}-{uuid4().hex[:4]}")
    db_session.add(tenant)
    await db_session.commit()
    return tenant


async def _create_user(
    db_session: AsyncSession,
    tenant_id=None,
    role: UserRoles = UserRoles.CAREGIVER,
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    user = User(
        id=uuid4(),
        tenant_id=tenant_id,
        keycloak_subject=f"sub-{uuid4().hex[:8]}",
        email=f"{uuid4().hex[:6]}@test.com",
        role=role,
        status=status,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _create_invitation(
    db_session: AsyncSession,
    tenant_id,
    sender_id,
    status: InviteStatus = InviteStatus.PENDING,
) -> Invitation:
    inv = Invitation(
        id=uuid4(),
        tenant_id=tenant_id,
        code=f"{uuid4().int % 1000000:06d}",
        expires_at=datetime.now(tz=UTC) + timedelta(minutes=10),
        status=status,
        sended_by_user_id=sender_id,
    )
    db_session.add(inv)
    await db_session.commit()
    return inv


# ==============================================================================
# get_stats
# ==============================================================================


class TestGetStats:

    async def test_stats_empty_tenant(self, db_session: AsyncSession) -> None:
        """Stats d'un tenant vide."""
        tenant = await _create_tenant(db_session)
        svc = _make_svc()

        stats = await svc.get_stats(tenant.id)

        assert stats.member_count == 0
        assert stats.patient_count == 0
        assert stats.box_count == 0
        assert stats.invitation_count == 0

    async def test_stats_with_members(self, db_session: AsyncSession) -> None:
        """Stats avec plusieurs membres."""
        tenant = await _create_tenant(db_session)
        await _create_user(db_session, tenant.id, UserRoles.TENANT_ADMIN)
        await _create_user(db_session, tenant.id, UserRoles.CAREGIVER)
        await _create_user(db_session, tenant.id, UserRoles.CAREGIVER)
        svc = _make_svc()

        stats = await svc.get_stats(tenant.id)

        assert stats.member_count == 3
        assert stats.admin_count == 1
        assert stats.caregiver_count == 2

    async def test_stats_with_invitations(self, db_session: AsyncSession) -> None:
        """Stats avec invitations."""
        tenant = await _create_tenant(db_session)
        sender = await _create_user(db_session, tenant.id)
        await _create_invitation(db_session, tenant.id, sender.id, InviteStatus.PENDING)
        await _create_invitation(db_session, tenant.id, sender.id, InviteStatus.CLAIMED)
        svc = _make_svc()

        stats = await svc.get_stats(tenant.id)

        assert stats.invitation_count == 2
        assert stats.pending_invitation_count == 1


# ==============================================================================
# list_members
# ==============================================================================


class TestListMembers:

    async def test_list_members(self, db_session: AsyncSession) -> None:
        """Liste les membres d'un tenant."""
        tenant = await _create_tenant(db_session)
        await _create_user(db_session, tenant.id, UserRoles.TENANT_ADMIN)
        await _create_user(db_session, tenant.id, UserRoles.CAREGIVER)
        svc = _make_svc()

        result = await svc.list_members(tenant.id)

        assert result.total == 2
        assert len(result.members) == 2

    async def test_list_members_empty(self, db_session: AsyncSession) -> None:
        """Tenant sans membres."""
        tenant = await _create_tenant(db_session)
        svc = _make_svc()

        result = await svc.list_members(tenant.id)

        assert result.total == 0
        assert result.members == []


# ==============================================================================
# update_member_role
# ==============================================================================


class TestUpdateMemberRole:

    async def test_update_role(self, db_session: AsyncSession) -> None:
        """Change le rôle d'un membre."""
        tenant = await _create_tenant(db_session)
        admin = await _create_user(db_session, tenant.id, UserRoles.TENANT_ADMIN)
        member = await _create_user(db_session, tenant.id, UserRoles.CAREGIVER)
        svc = _make_svc()

        result = await svc.update_member_role(
            tenant.id,
            member.id,
            UserRoles.PATIENT,
            admin.id,
        )

        assert result.role == UserRoles.PATIENT.value

    async def test_cannot_modify_self(self, db_session: AsyncSession) -> None:
        """Lève 400 si l'admin tente de modifier son propre rôle."""
        tenant = await _create_tenant(db_session)
        admin = await _create_user(db_session, tenant.id, UserRoles.TENANT_ADMIN)
        svc = _make_svc()

        with pytest.raises(HTTPException) as exc_info:
            await svc.update_member_role(
                tenant.id,
                admin.id,
                UserRoles.CAREGIVER,
                admin.id,
            )
        assert exc_info.value.status_code == 400

    async def test_cannot_modify_admin(self, db_session: AsyncSession) -> None:
        """Lève 400 si on tente de modifier un admin."""
        tenant = await _create_tenant(db_session)
        admin1 = await _create_user(db_session, tenant.id, UserRoles.TENANT_ADMIN)
        admin2 = await _create_user(db_session, tenant.id, UserRoles.TENANT_ADMIN)
        svc = _make_svc()

        with pytest.raises(HTTPException) as exc_info:
            await svc.update_member_role(
                tenant.id,
                admin2.id,
                UserRoles.CAREGIVER,
                admin1.id,
            )
        assert exc_info.value.status_code == 400

    async def test_member_not_in_tenant(self, db_session: AsyncSession) -> None:
        """Lève 404 si le membre n'appartient pas au tenant."""
        tenant = await _create_tenant(db_session)
        admin = await _create_user(db_session, tenant.id, UserRoles.TENANT_ADMIN)
        other_user = await _create_user(db_session, tenant_id=None)
        svc = _make_svc()

        with pytest.raises(HTTPException) as exc_info:
            await svc.update_member_role(
                tenant.id,
                other_user.id,
                UserRoles.CAREGIVER,
                admin.id,
            )
        assert exc_info.value.status_code == 404

    async def test_cannot_promote_to_admin(self, db_session: AsyncSession) -> None:
        """Lève 400 si on tente de promouvoir en TENANT_ADMIN."""
        tenant = await _create_tenant(db_session)
        admin = await _create_user(db_session, tenant.id, UserRoles.TENANT_ADMIN)
        member = await _create_user(db_session, tenant.id, UserRoles.CAREGIVER)
        svc = _make_svc()

        with pytest.raises(HTTPException) as exc_info:
            await svc.update_member_role(
                tenant.id,
                member.id,
                UserRoles.TENANT_ADMIN,
                admin.id,
            )
        assert exc_info.value.status_code == 400


# ==============================================================================
# remove_member
# ==============================================================================


class TestRemoveMember:

    async def test_remove_member(self, db_session: AsyncSession) -> None:
        """Retire un membre du tenant."""
        tenant = await _create_tenant(db_session)
        admin = await _create_user(db_session, tenant.id, UserRoles.TENANT_ADMIN)
        member = await _create_user(db_session, tenant.id, UserRoles.CAREGIVER)
        svc = _make_svc()

        await svc.remove_member(tenant.id, member.id, admin.id)

        user_repo = UserRepository()
        updated = await user_repo.get(member.id)
        assert updated.tenant_id is None
        assert updated.role == UserRoles.DEFAULT

    async def test_cannot_remove_self(self, db_session: AsyncSession) -> None:
        """Lève 400 si l'admin tente de se retirer."""
        tenant = await _create_tenant(db_session)
        admin = await _create_user(db_session, tenant.id, UserRoles.TENANT_ADMIN)
        svc = _make_svc()

        with pytest.raises(HTTPException) as exc_info:
            await svc.remove_member(tenant.id, admin.id, admin.id)
        assert exc_info.value.status_code == 400

    async def test_cannot_remove_admin(self, db_session: AsyncSession) -> None:
        """Lève 400 si on tente de retirer un admin."""
        tenant = await _create_tenant(db_session)
        admin1 = await _create_user(db_session, tenant.id, UserRoles.TENANT_ADMIN)
        admin2 = await _create_user(db_session, tenant.id, UserRoles.TENANT_ADMIN)
        svc = _make_svc()

        with pytest.raises(HTTPException) as exc_info:
            await svc.remove_member(tenant.id, admin2.id, admin1.id)
        assert exc_info.value.status_code == 400

    async def test_remove_member_not_found(self, db_session: AsyncSession) -> None:
        """Lève 404 si le membre n'existe pas dans le tenant."""
        tenant = await _create_tenant(db_session)
        admin = await _create_user(db_session, tenant.id, UserRoles.TENANT_ADMIN)
        svc = _make_svc()

        with pytest.raises(HTTPException) as exc_info:
            await svc.remove_member(tenant.id, uuid4(), admin.id)
        assert exc_info.value.status_code == 404


# ==============================================================================
# get_invitation_history
# ==============================================================================


class TestInvitationHistory:

    async def test_invitation_history(self, db_session: AsyncSession) -> None:
        """Retourne l'historique des invitations."""
        tenant = await _create_tenant(db_session)
        sender = await _create_user(db_session, tenant.id)
        await _create_invitation(db_session, tenant.id, sender.id, InviteStatus.PENDING)
        await _create_invitation(db_session, tenant.id, sender.id, InviteStatus.CLAIMED)
        svc = _make_svc()

        result = await svc.get_invitation_history(tenant.id)

        assert result.total == 2
        assert len(result.invitations) == 2

    async def test_invitation_history_empty(self, db_session: AsyncSession) -> None:
        """Historique vide si aucune invitation."""
        tenant = await _create_tenant(db_session)
        svc = _make_svc()

        result = await svc.get_invitation_history(tenant.id)

        assert result.total == 0
        assert result.invitations == []

    async def test_invitation_history_pagination(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Pagination de l'historique."""
        tenant = await _create_tenant(db_session)
        sender = await _create_user(db_session, tenant.id)
        for _ in range(5):
            await _create_invitation(db_session, tenant.id, sender.id)
        svc = _make_svc()

        # Limit 3
        result = await svc.get_invitation_history(tenant.id, limit=3)
        assert result.total == 5
        assert len(result.invitations) == 3
