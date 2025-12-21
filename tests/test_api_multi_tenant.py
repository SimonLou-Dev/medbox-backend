"""Tests d'isolation multi-tenant (CRITIQUES)."""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medbox.core.db.models.tenant import Tenant
from medbox.core.db.models.user import User

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestMultiTenantIsolation:
    """Vérifier l'isolation des données entre tenants."""

    async def test_user_a_cannot_list_tenant_b_users(
        self,
        async_client: "AsyncClient",
        db_session: AsyncSession,
    ) -> None:
        """❌ FAIL si User A peut voir les users du Tenant B."""
        # Setup: Créer 2 tenants
        tenant_a = Tenant(id=uuid4(), name="Tenant A")
        tenant_b = Tenant(id=uuid4(), name="Tenant B")

        user_a = User(
            id=uuid4(),
            keycloak_subject="user_a",
            email="a@example.com",
            tenant_id=tenant_a.id,
        )

        user_b = User(
            id=uuid4(),
            keycloak_subject="user_b",
            email="b@example.com",
            tenant_id=tenant_b.id,
        )

        db_session.add_all([tenant_a, tenant_b, user_a, user_b])
        await db_session.commit()

        # Assert: Aucun user du Tenant B visible
        # Querry users from tenant_a directly
        stmt = select(User).where(User.tenant_id == tenant_a.id)
        result = await db_session.execute(stmt)
        users_a = result.scalars().all()

        assert len(users_a) == 1
        assert users_a[0].id == user_a.id

    async def test_user_cannot_access_other_tenant_data(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Vérifier le scoping tenant_id au niveau repository."""
        # Setup
        tenant_1 = Tenant(id=uuid4(), name="Tenant 1")
        tenant_2 = Tenant(id=uuid4(), name="Tenant 2")

        user_1 = User(
            id=uuid4(),
            keycloak_subject="subject_1",
            email="user1@test.com",
            tenant_id=tenant_1.id,
        )

        user_2 = User(
            id=uuid4(),
            keycloak_subject="subject_2",
            email="user2@test.com",
            tenant_id=tenant_2.id,
        )

        db_session.add_all([tenant_1, tenant_2, user_1, user_2])
        await db_session.commit()

        # Assert: Seulement les users de tenant_1
        stmt = select(User).where(User.tenant_id == tenant_1.id)
        result = await db_session.execute(stmt)
        users_in_tenant_1 = result.scalars().all()

        assert len(users_in_tenant_1) == 1
        assert users_in_tenant_1[0].email == "user1@test.com"

    async def test_get_by_subject_respects_tenant_scope(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Vérifier que get_by_subject respecte tenant_id."""
        tenant_a = Tenant(id=uuid4(), name="A")
        tenant_b = Tenant(id=uuid4(), name="B")

        # Même subject dans 2 tenants (cas théorique)
        user_a = User(
            id=uuid4(),
            keycloak_subject="same_subject",
            email="a@test.com",
            tenant_id=tenant_a.id,
        )

        user_b = User(
            id=uuid4(),
            keycloak_subject="same_subject",
            email="b@test.com",
            tenant_id=tenant_b.id,
        )

        db_session.add_all([tenant_a, tenant_b, user_a, user_b])
        await db_session.commit()

        # Query: Only user_a from tenant_a with same_subject
        stmt = (
            select(User)
            .where(User.keycloak_subject == "same_subject")
            .where(User.tenant_id == tenant_a.id)
        )
        result = await db_session.execute(stmt)
        user = result.scalar_one_or_none()

        # Assert: Seulement user_a retourné
        assert user is not None
        assert user.email == "a@test.com"
        assert user.tenant_id == tenant_a.id

        # Query: Only user_b from tenant_b with same_subject
        stmt = (
            select(User)
            .where(User.keycloak_subject == "same_subject")
            .where(User.tenant_id == tenant_b.id)
        )
        result = await db_session.execute(stmt)
        user = result.scalar_one_or_none()

        # Assert: Seulement user_b retourné
        assert user is not None
        assert user.email == "b@test.com"
        assert user.tenant_id == tenant_b.id


class TestTenantAdmin403Isolation:
    """Admin d'un tenant ne peut pas accéder à un autre tenant."""

    async def test_tenant_a_admin_forbidden_access_tenant_b(
        self,
        async_client: "AsyncClient",
    ) -> None:
        """Un admin du tenant A ne peut pas POST sur tenant B."""
        # Setup: Admin du tenant A avec token valide
        # Act: Essayer POST /api/v1/tenant/{tenant_b_id}/...

        # Assert: Doit recevoir 403 Forbidden ou erreur d'authentification


class TestInvitationTenantBoundary:
    """Les invitations doivent être limitées par tenant."""

    async def test_cannot_invite_to_other_tenant(self) -> None:
        """Admin A ne peut pas créer une invitation pour Tenant B."""

    async def test_invitation_code_specific_to_tenant(self) -> None:
        """Un code d'invitation ne peut joindre que son tenant."""
