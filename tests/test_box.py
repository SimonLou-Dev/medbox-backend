"""Tests d'intégration pour BoxService."""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from medbox.core.db.models.patient import Patient
from medbox.core.db.models.tenant import Tenant
from medbox.core.dto.box import BoxRequest, BoxStatusUpdateRequest
from medbox.core.services.box import BoxService

pytestmark = pytest.mark.asyncio


# ==============================================================================
# Helpers
# ==============================================================================


async def _setup_tenant(db_session: AsyncSession) -> Tenant:
    tenant = Tenant(id=uuid4(), name=f"Tenant-{uuid4().hex[:6]}")
    db_session.add(tenant)
    await db_session.commit()
    return tenant


async def _setup_tenant_and_patient(
    db_session: AsyncSession,
) -> tuple[Tenant, Patient]:
    tenant = await _setup_tenant(db_session)
    patient = Patient(
        id=uuid4(),
        tenant_id=tenant.id,
        c_first_name="Alice",
        c_last_name="Dupont",
    )
    db_session.add(patient)
    await db_session.commit()
    return tenant, patient


def _svc(tenant_id) -> BoxService:
    return BoxService(tenant_id=tenant_id)


def _req(**kwargs) -> BoxRequest:
    defaults = {
        "box_uid": f"BOX-{uuid4().hex[:8]}",
        "name": "Boîte principale",
        "status": "active",
    }
    defaults.update(kwargs)
    return BoxRequest(**defaults)


# ==============================================================================
# CRUD
# ==============================================================================


class TestBoxCRUD:
    async def test_create_and_get(self, db_session: AsyncSession) -> None:
        """Crée une box et la récupère."""
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        created = await svc.create(_req(name="Box Test", status="active"))

        assert created.name == "Box Test"
        assert created.status == "active"
        assert created.tenant_id == tenant.id

        retrieved = await svc.get(created.id)
        assert retrieved.id == created.id
        assert retrieved.name == "Box Test"

    async def test_list(self, db_session: AsyncSession) -> None:
        """Liste les boxes du tenant."""
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        await svc.create(_req(box_uid="BOX-001"))
        await svc.create(_req(box_uid="BOX-002"))
        await svc.create(_req(box_uid="BOX-003"))

        result = await svc.list()
        assert len(result) == 3

    async def test_update(self, db_session: AsyncSession) -> None:
        """Met à jour une box."""
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        created = await svc.create(_req(box_uid="BOX-001", name="Avant"))
        updated = await svc.update(
            created.id,
            _req(box_uid="BOX-001", name="Après", status="inactive"),
        )

        assert updated.name == "Après"
        assert updated.status == "inactive"

    async def test_update_status(self, db_session: AsyncSession) -> None:
        """Met à jour uniquement le statut."""
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        created = await svc.create(_req(status="active"))
        updated = await svc.update_status(
            created.id,
            BoxStatusUpdateRequest(status="maintenance"),
        )

        assert updated.status == "maintenance"
        assert updated.name == created.name  # inchangé

    async def test_delete(self, db_session: AsyncSession) -> None:
        """Supprime une box."""
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        created = await svc.create(_req())
        box_id = created.id

        result = await svc.delete(box_id)
        assert result is True

        with pytest.raises(HTTPException) as exc_info:
            await svc.get(box_id)
        assert exc_info.value.status_code == 404

    async def test_create_with_patient(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Crée une box associée à un patient."""
        tenant, patient = await _setup_tenant_and_patient(db_session)
        svc = _svc(tenant.id)

        created = await svc.create(_req(patient_id=patient.id))
        assert created.patient_id == patient.id


# ==============================================================================
# Erreurs
# ==============================================================================


class TestBoxErrors:
    async def test_get_not_found(self, db_session: AsyncSession) -> None:
        """Lève 404 si la box n'existe pas."""
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        with pytest.raises(HTTPException) as exc_info:
            await svc.get(uuid4())
        assert exc_info.value.status_code == 404

    async def test_create_duplicate_uid(self, db_session: AsyncSession) -> None:
        """Lève 409 si le box_uid est déjà pris."""
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        await svc.create(_req(box_uid="BOX-DUP"))

        with pytest.raises(HTTPException) as exc_info:
            await svc.create(_req(box_uid="BOX-DUP"))
        assert exc_info.value.status_code == 409

    async def test_update_not_found(self, db_session: AsyncSession) -> None:
        """Lève 404 si la box à mettre à jour n'existe pas."""
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        with pytest.raises(HTTPException) as exc_info:
            await svc.update(uuid4(), _req())
        assert exc_info.value.status_code == 404

    async def test_delete_not_found(self, db_session: AsyncSession) -> None:
        """Lève 404 si la box à supprimer n'existe pas."""
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        with pytest.raises(HTTPException) as exc_info:
            await svc.delete(uuid4())
        assert exc_info.value.status_code == 404


# ==============================================================================
# Isolation multi-tenant
# ==============================================================================


class TestBoxTenantIsolation:
    async def test_tenant_isolation(self, db_session: AsyncSession) -> None:
        """Un tenant ne peut pas voir les boxes d'un autre tenant."""
        tenant_a = Tenant(id=uuid4(), name="TenantA")
        tenant_b = Tenant(id=uuid4(), name="TenantB")
        db_session.add_all([tenant_a, tenant_b])
        await db_session.commit()

        svc_a = _svc(tenant_a.id)
        svc_b = _svc(tenant_b.id)

        await svc_a.create(_req(box_uid="BOX-A1"))
        await svc_a.create(_req(box_uid="BOX-A2"))
        await svc_b.create(_req(box_uid="BOX-B1"))

        list_a = await svc_a.list()
        list_b = await svc_b.list()

        assert len(list_a) == 2
        assert len(list_b) == 1

    async def test_get_other_tenant_box_returns_404(
        self,
        db_session: AsyncSession,
    ) -> None:
        """get() sur une box d'un autre tenant lève 404."""
        tenant_a = Tenant(id=uuid4(), name="TenantA2")
        tenant_b = Tenant(id=uuid4(), name="TenantB2")
        db_session.add_all([tenant_a, tenant_b])
        await db_session.commit()

        svc_a = _svc(tenant_a.id)
        svc_b = _svc(tenant_b.id)

        box = await svc_a.create(_req(box_uid="BOX-CROSS"))

        with pytest.raises(HTTPException) as exc_info:
            await svc_b.get(box.id)
        assert exc_info.value.status_code == 404
