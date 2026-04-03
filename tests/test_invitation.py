"""Tests d'intégration pour TenantInvitationService."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from medbox.core.constants.enums import InviteStatus, UserStatus
from medbox.core.db.models.invitation import Invitation
from medbox.core.db.models.tenant import Tenant
from medbox.core.db.models.user import User
from medbox.core.db.repositories.invitation import InvitationRepository
from medbox.core.db.repositories.tenant import TenantRepository
from medbox.core.db.repositories.user import UserRepository
from medbox.core.exceptions import ModelNotFoundError
from medbox.core.services.tenant_invitation import TenantInvitationService

pytestmark = pytest.mark.asyncio


# ==============================================================================
# Helpers
# ==============================================================================


def _make_svc() -> TenantInvitationService:
    return TenantInvitationService(
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
    status: UserStatus = UserStatus.PENDING,
) -> User:
    user = User(
        id=uuid4(),
        tenant_id=tenant_id,
        keycloak_subject=f"sub-{uuid4().hex[:8]}",
        email=f"{uuid4().hex[:6]}@test.com",
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
    expires_delta: timedelta = timedelta(minutes=10),
) -> Invitation:
    inv = Invitation(
        id=uuid4(),
        tenant_id=tenant_id,
        code=f"{uuid4().int % 1000000:06d}",
        expires_at=datetime.now(tz=UTC) + expires_delta,
        status=status,
        sended_by_user_id=sender_id,
    )
    db_session.add(inv)
    await db_session.commit()
    return inv


# ==============================================================================
# generate_invite_code
# ==============================================================================


class TestGenerateInviteCode:

    async def test_generate_code(self, db_session: AsyncSession) -> None:
        """Génère un code d'invitation valide."""
        tenant = await _create_tenant(db_session)
        sender = await _create_user(db_session, tenant_id=tenant.id)
        svc = _make_svc()

        with patch(
            "medbox.core.tasks.invitation_tasks.expire_invitation.apply_async"
        ):
            invite = await svc.generate_invite_code(sender, tenant.id)

        assert invite.tenant_id == tenant.id
        assert invite.status == InviteStatus.PENDING
        assert len(invite.code) == 6
        assert invite.code.isdigit()

    async def test_generate_expires_previous(self, db_session: AsyncSession) -> None:
        """Génère un nouveau code et expire l'ancien."""
        tenant = await _create_tenant(db_session)
        sender = await _create_user(db_session, tenant_id=tenant.id)
        existing = await _create_invitation(db_session, tenant.id, sender.id)
        svc = _make_svc()

        with patch(
            "medbox.core.tasks.invitation_tasks.expire_invitation.apply_async"
        ):
            new_invite = await svc.generate_invite_code(sender, tenant.id)

        # L'ancien code doit être expiré
        invite_repo = InvitationRepository()
        old = await invite_repo.get(existing.id)
        assert old.status == InviteStatus.EXPIRED

        # Le nouveau code est actif
        assert new_invite.status == InviteStatus.PENDING
        assert new_invite.id != existing.id


# ==============================================================================
# claim_invitation
# ==============================================================================


class TestClaimInvitation:

    async def test_claim_valid_code(self, db_session: AsyncSession) -> None:
        """Un utilisateur rejoint le tenant avec un code valide."""
        tenant = await _create_tenant(db_session)
        sender = await _create_user(db_session, tenant_id=tenant.id)
        claimer = await _create_user(db_session, tenant_id=None)
        invite = await _create_invitation(db_session, tenant.id, sender.id)
        svc = _make_svc()

        result = await svc.claim_invitation(invite.code, claimer)
        assert result is True

        # L'invitation est marquée CLAIMED
        invite_repo = InvitationRepository()
        updated = await invite_repo.get(invite.id)
        assert updated.status == InviteStatus.CLAIMED
        assert updated.claimed_by_user_id == claimer.id

        # Le user est maintenant actif
        user_repo = UserRepository()
        updated_user = await user_repo.get(claimer.id)
        assert updated_user.status == UserStatus.ACTIVE
        assert updated_user.tenant_id == tenant.id

    async def test_claim_invalid_code(self, db_session: AsyncSession) -> None:
        """Lève 404 si le code est invalide."""
        user = await _create_user(db_session)
        svc = _make_svc()

        with pytest.raises(HTTPException) as exc_info:
            await svc.claim_invitation("999999", user)
        assert exc_info.value.status_code == 404

    async def test_claim_expired_invitation(self, db_session: AsyncSession) -> None:
        """Lève 400 si l'invitation est expirée."""
        tenant = await _create_tenant(db_session)
        sender = await _create_user(db_session, tenant_id=tenant.id)
        claimer = await _create_user(db_session, tenant_id=None)
        invite = await _create_invitation(
            db_session,
            tenant.id,
            sender.id,
            expires_delta=timedelta(seconds=-1),  # déjà expiré
        )
        svc = _make_svc()

        with pytest.raises(HTTPException) as exc_info:
            await svc.claim_invitation(invite.code, claimer)
        assert exc_info.value.status_code == 400

    async def test_claim_already_claimed(self, db_session: AsyncSession) -> None:
        """Lève 400 si l'invitation a déjà été utilisée."""
        tenant = await _create_tenant(db_session)
        sender = await _create_user(db_session, tenant_id=tenant.id)
        claimer = await _create_user(db_session, tenant_id=None)
        invite = await _create_invitation(
            db_session,
            tenant.id,
            sender.id,
            status=InviteStatus.CLAIMED,
        )
        svc = _make_svc()

        with pytest.raises(HTTPException) as exc_info:
            await svc.claim_invitation(invite.code, claimer)
        assert exc_info.value.status_code == 400


# ==============================================================================
# revoke_invitation
# ==============================================================================


class TestRevokeInvitation:

    async def test_revoke_invitation(self, db_session: AsyncSession) -> None:
        """Annule une invitation active."""
        tenant = await _create_tenant(db_session)
        sender = await _create_user(db_session, tenant_id=tenant.id)
        invite = await _create_invitation(db_session, tenant.id, sender.id)
        svc = _make_svc()

        await svc.revoke_invitation(invite.id)

        invite_repo = InvitationRepository()
        updated = await invite_repo.get(invite.id)
        assert updated.status == InviteStatus.CANCELED

    async def test_revoke_not_found(self, db_session: AsyncSession) -> None:
        """Lève 404 si l'invitation n'existe pas."""
        svc = _make_svc()

        with pytest.raises(HTTPException) as exc_info:
            await svc.revoke_invitation(uuid4())
        assert exc_info.value.status_code == 404


# ==============================================================================
# expire_invitation
# ==============================================================================


class TestExpireInvitation:

    async def test_expire_invitation(self, db_session: AsyncSession) -> None:
        """Marque une invitation comme expirée."""
        tenant = await _create_tenant(db_session)
        sender = await _create_user(db_session, tenant_id=tenant.id)
        invite = await _create_invitation(db_session, tenant.id, sender.id)
        svc = _make_svc()

        await svc.expire_invitation(invite.id)

        invite_repo = InvitationRepository()
        updated = await invite_repo.get(invite.id)
        assert updated.status == InviteStatus.EXPIRED

    async def test_expire_not_found_raises(self, db_session: AsyncSession) -> None:
        """Lève ModelNotFoundError si l'invitation n'existe pas."""
        svc = _make_svc()

        with pytest.raises(ModelNotFoundError):
            await svc.expire_invitation(uuid4())


# ==============================================================================
# get_active_code
# ==============================================================================


class TestGetActiveCode:

    async def test_get_active_code(self, db_session: AsyncSession) -> None:
        """Retourne le code actif du tenant."""
        tenant = await _create_tenant(db_session)
        sender = await _create_user(db_session, tenant_id=tenant.id)
        invite = await _create_invitation(db_session, tenant.id, sender.id)
        svc = _make_svc()

        active = await svc.get_active_code(tenant.id)
        assert active is not None
        assert active.id == invite.id

    async def test_get_active_code_none(self, db_session: AsyncSession) -> None:
        """Retourne None si aucun code actif."""
        tenant = await _create_tenant(db_session)
        svc = _make_svc()

        active = await svc.get_active_code(tenant.id)
        assert active is None

    async def test_get_active_code_ignores_expired(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Ignore les invitations expirées."""
        tenant = await _create_tenant(db_session)
        sender = await _create_user(db_session, tenant_id=tenant.id)
        await _create_invitation(
            db_session,
            tenant.id,
            sender.id,
            expires_delta=timedelta(seconds=-1),
        )
        svc = _make_svc()

        active = await svc.get_active_code(tenant.id)
        assert active is None
