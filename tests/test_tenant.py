"""Tests d'intégration pour TenantService."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from medbox.core.constants.enums import UserRoles, UserStatus
from medbox.core.db.models.tenant import Tenant
from medbox.core.db.models.user import User
from medbox.core.db.repositories.tenant import TenantRepository
from medbox.core.db.repositories.user import UserRepository
from medbox.core.dto.tenant import TenantRequest
from medbox.core.services.tenant import TenantService

pytestmark = pytest.mark.asyncio


# ==============================================================================
# Helpers
# ==============================================================================


def _make_svc() -> TenantService:
    """Service avec dépendances mockées."""
    return TenantService(
        tenant_invit_svc=AsyncMock(),
        tenant_right_svc=AsyncMock(),
        tenant_repo=TenantRepository(),
        user_repo=UserRepository(),
    )


async def _create_tenant(db_session: AsyncSession, name: str = "Tenant Test") -> Tenant:
    tenant = Tenant(id=uuid4(), name=name)
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


# ==============================================================================
# get / update
# ==============================================================================


class TestTenantGetUpdate:
    async def test_get_tenant(self, db_session: AsyncSession) -> None:
        """Récupère un tenant avec ses compteurs."""
        tenant = await _create_tenant(db_session, "Clinique A")
        svc = _make_svc()

        result = await svc.get(tenant.id)

        assert result.id == tenant.id
        assert result.name == "Clinique A"
        assert result.patient_count == 0
        assert result.box_count == 0

    async def test_update_tenant_name(self, db_session: AsyncSession) -> None:
        """Met à jour le nom d'un tenant."""
        tenant = await _create_tenant(db_session, "Ancien Nom")
        svc = _make_svc()

        updated = await svc.update(tenant.id, TenantRequest(name="Nouveau Nom"))

        assert updated.name == "Nouveau Nom"

    async def test_update_not_found(self, db_session: AsyncSession) -> None:
        """Lève 404 si le tenant n'existe pas."""
        svc = _make_svc()

        with pytest.raises(HTTPException) as exc_info:
            await svc.update(uuid4(), TenantRequest(name="X"))
        assert exc_info.value.status_code == 404


# ==============================================================================
# delete
# ==============================================================================


class TestTenantDelete:
    async def test_delete_tenant(self, db_session: AsyncSession) -> None:
        """Supprime un tenant."""
        tenant = await _create_tenant(db_session, "A supprimer")
        svc = _make_svc()

        result = await svc.delete(tenant.id)
        assert result is True

    async def test_delete_resets_users(self, db_session: AsyncSession) -> None:
        """La suppression d'un tenant remet les utilisateurs à DEFAULT/PENDING."""
        tenant = await _create_tenant(db_session, "Tenant Avec Users")
        user = await _create_user(
            db_session,
            tenant_id=tenant.id,
            role=UserRoles.CAREGIVER,
            status=UserStatus.ACTIVE,
        )
        svc = _make_svc()

        await svc.delete(tenant.id)

        user_repo = UserRepository()
        updated_user = await user_repo.get(user.id)
        assert updated_user.role == UserRoles.DEFAULT
        assert updated_user.status == UserStatus.PENDING
        assert updated_user.tenant_id is None

    async def test_delete_not_found(self, db_session: AsyncSession) -> None:
        """Lève 404 si le tenant n'existe pas."""
        svc = _make_svc()

        with pytest.raises(HTTPException) as exc_info:
            await svc.delete(uuid4())
        assert exc_info.value.status_code == 404


# ==============================================================================
# leave_tenant
# ==============================================================================


class TestLeaveTenant:
    async def test_leave_tenant_success(self, db_session: AsyncSession) -> None:
        """Un CAREGIVER peut quitter son tenant."""
        tenant = await _create_tenant(db_session, "Tenant Quitter")
        user = await _create_user(
            db_session,
            tenant_id=tenant.id,
            role=UserRoles.CAREGIVER,
        )
        svc = _make_svc()

        await svc.leave_tenant(user.keycloak_subject)

        user_repo = UserRepository()
        updated = await user_repo.get(user.id)
        assert updated.tenant_id is None
        assert updated.role == UserRoles.DEFAULT

    async def test_leave_tenant_no_tenant(self, db_session: AsyncSession) -> None:
        """Lève 400 si l'utilisateur n'est dans aucun tenant."""
        user = await _create_user(db_session, tenant_id=None)
        svc = _make_svc()

        with pytest.raises(HTTPException) as exc_info:
            await svc.leave_tenant(user.keycloak_subject)
        assert exc_info.value.status_code == 400

    async def test_leave_tenant_admin_forbidden(self, db_session: AsyncSession) -> None:
        """Un TENANT_ADMIN ne peut pas quitter son tenant."""
        tenant = await _create_tenant(db_session, "Tenant Admin")
        user = await _create_user(
            db_session,
            tenant_id=tenant.id,
            role=UserRoles.TENANT_ADMIN,
        )
        svc = _make_svc()

        with pytest.raises(HTTPException) as exc_info:
            await svc.leave_tenant(user.keycloak_subject)
        assert exc_info.value.status_code == 403


# ==============================================================================
# create
# ==============================================================================


class TestTenantCreate:
    async def test_create_tenant(self, db_session: AsyncSession) -> None:
        """Crée un tenant et nomme l'utilisateur admin."""
        user = await _create_user(db_session, tenant_id=None, status=UserStatus.PENDING)

        # Mock des sous-services
        mock_invit_svc = AsyncMock()
        mock_invit_svc.add_user_to_tenant.return_value = user
        mock_right_svc = AsyncMock()
        mock_right_svc.set_user_role.return_value = user

        svc = TenantService(
            tenant_invit_svc=mock_invit_svc,
            tenant_right_svc=mock_right_svc,
            tenant_repo=TenantRepository(),
            user_repo=UserRepository(),
        )

        from medbox.core.services.security import UserContext

        ctx = UserContext(
            claims={"sub": user.keycloak_subject, "email": user.email},
            token="test-token",  # noqa: S106
        )

        tenant, _ = await svc.create(TenantRequest(name="Nouveau Tenant"), ctx)

        assert tenant.name == "Nouveau Tenant"
        mock_invit_svc.add_user_to_tenant.assert_called_once()
        mock_right_svc.set_user_role.assert_called_once()

    async def test_create_tenant_already_in_tenant(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Lève 400 si l'utilisateur est déjà dans un tenant."""
        existing_tenant = await _create_tenant(db_session, "Existant")
        user = await _create_user(db_session, tenant_id=existing_tenant.id)
        svc = _make_svc()

        from medbox.core.services.security import UserContext

        ctx = UserContext(
            claims={"sub": user.keycloak_subject, "email": user.email},
            token="test-token",  # noqa: S106
        )

        with pytest.raises(HTTPException) as exc_info:
            await svc.create(TenantRequest(name="Nouveau"), ctx)
        assert exc_info.value.status_code == 400
