"""Tests d'intégration pour WheelService."""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from medbox.core.db.models.tenant import Tenant
from medbox.core.dto.wheel import (
    WheelRequest,
    WheelSlotUpdateRequest,
    WheelStatusUpdateRequest,
)
from medbox.core.services.wheel import WheelService

pytestmark = pytest.mark.asyncio


# ==============================================================================
# Helpers
# ==============================================================================


async def _setup_tenant(db_session: AsyncSession) -> Tenant:
    tenant = Tenant(id=uuid4(), name=f"Tenant-{uuid4().hex[:6]}")
    db_session.add(tenant)
    await db_session.commit()
    return tenant


def _svc(tenant_id) -> WheelService:
    return WheelService(tenant_id=tenant_id)


def _req(**kwargs) -> WheelRequest:
    defaults = {
        "wheel_uid": f"WHEEL-{uuid4().hex[:8]}",
        "slot_count": 28,
        "status": "prepared",
    }
    defaults.update(kwargs)
    return WheelRequest(**defaults)


# ==============================================================================
# CRUD Roues
# ==============================================================================


class TestWheelCRUD:
    async def test_create_and_get(self, db_session: AsyncSession) -> None:
        """Crée une roue et la récupère avec ses slots."""
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        created = await svc.create(_req(slot_count=28))

        assert created.tenant_id == tenant.id
        assert created.slot_count == 28
        assert len(created.slots) == 28
        # Les indices des slots vont de 0 à 27
        indices = sorted(s.index for s in created.slots)
        assert indices == list(range(28))

        retrieved = await svc.get(created.id)
        assert retrieved.id == created.id
        assert len(retrieved.slots) == 28

    async def test_create_custom_slot_count(self, db_session: AsyncSession) -> None:
        """Crée une roue avec un nombre de slots personnalisé."""
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        created = await svc.create(_req(slot_count=7))
        assert len(created.slots) == 7

    async def test_list(self, db_session: AsyncSession) -> None:
        """Liste les roues du tenant."""
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        await svc.create(_req(wheel_uid="W-001"))
        await svc.create(_req(wheel_uid="W-002"))

        result = await svc.list()
        assert len(result) == 2

    async def test_update(self, db_session: AsyncSession) -> None:
        """Met à jour une roue (status, associations)."""
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        created = await svc.create(_req(wheel_uid="W-UPD", status="prepared"))
        updated = await svc.update(
            created.id,
            _req(wheel_uid="W-UPD", status="mounted"),
        )

        assert updated.status == "mounted"
        assert updated.id == created.id

    async def test_update_status(self, db_session: AsyncSession) -> None:
        """Met à jour uniquement le statut."""
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        created = await svc.create(_req(status="prepared"))
        updated = await svc.update_status(
            created.id,
            WheelStatusUpdateRequest(status="in_stock"),
        )

        assert updated.status == "in_stock"

    async def test_delete(self, db_session: AsyncSession) -> None:
        """Supprime une roue."""
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        created = await svc.create(_req())
        wheel_id = created.id

        result = await svc.delete(wheel_id)
        assert result is True

        with pytest.raises(HTTPException) as exc_info:
            await svc.get(wheel_id)
        assert exc_info.value.status_code == 404


# ==============================================================================
# Gestion des slots
# ==============================================================================


class TestWheelSlots:
    async def test_list_slots(self, db_session: AsyncSession) -> None:
        """Liste les slots d'une roue."""
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        wheel = await svc.create(_req(slot_count=14))
        slots = await svc.list_slots(wheel.id)

        assert len(slots) == 14

    async def test_get_slot(self, db_session: AsyncSession) -> None:
        """Récupère un slot spécifique."""
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        wheel = await svc.create(_req(slot_count=5))
        slot_id = wheel.slots[0].id

        slot = await svc.get_slot(wheel.id, slot_id)
        assert slot.id == slot_id
        assert slot.wheel_id == wheel.id

    async def test_update_slot_label(self, db_session: AsyncSession) -> None:
        """Met à jour le label d'un slot."""
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        wheel = await svc.create(_req(slot_count=4))
        slot_id = wheel.slots[0].id

        updated = await svc.update_slot(
            wheel.id,
            slot_id,
            WheelSlotUpdateRequest(c_label="Matin"),
        )

        assert updated.c_label == "Matin"
        assert updated.id == slot_id

    async def test_update_slot_clear_label(self, db_session: AsyncSession) -> None:
        """Efface le label d'un slot."""
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        wheel = await svc.create(_req(slot_count=4))
        slot_id = wheel.slots[0].id

        # Set label
        await svc.update_slot(wheel.id, slot_id, WheelSlotUpdateRequest(c_label="Midi"))
        # Clear label
        cleared = await svc.update_slot(
            wheel.id,
            slot_id,
            WheelSlotUpdateRequest(c_label=None),
        )
        assert cleared.c_label is None

    async def test_get_slot_wrong_wheel_returns_404(
        self,
        db_session: AsyncSession,
    ) -> None:
        """get_slot() lève 404 si le slot n'appartient pas à la roue."""
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        wheel1 = await svc.create(_req(slot_count=4))
        wheel2 = await svc.create(_req(slot_count=4))

        # Slot de wheel1, demandé sur wheel2
        slot_id = wheel1.slots[0].id

        with pytest.raises(HTTPException) as exc_info:
            await svc.get_slot(wheel2.id, slot_id)
        assert exc_info.value.status_code == 404


# ==============================================================================
# Erreurs
# ==============================================================================


class TestWheelErrors:
    async def test_get_not_found(self, db_session: AsyncSession) -> None:
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        with pytest.raises(HTTPException) as exc_info:
            await svc.get(uuid4())
        assert exc_info.value.status_code == 404

    async def test_create_duplicate_uid(self, db_session: AsyncSession) -> None:
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        await svc.create(_req(wheel_uid="WHEEL-DUP"))

        with pytest.raises(HTTPException) as exc_info:
            await svc.create(_req(wheel_uid="WHEEL-DUP"))
        assert exc_info.value.status_code == 409

    async def test_update_not_found(self, db_session: AsyncSession) -> None:
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        with pytest.raises(HTTPException) as exc_info:
            await svc.update(uuid4(), _req())
        assert exc_info.value.status_code == 404

    async def test_delete_not_found(self, db_session: AsyncSession) -> None:
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        with pytest.raises(HTTPException) as exc_info:
            await svc.delete(uuid4())
        assert exc_info.value.status_code == 404

    async def test_list_slots_wheel_not_found(self, db_session: AsyncSession) -> None:
        tenant = await _setup_tenant(db_session)
        svc = _svc(tenant.id)

        with pytest.raises(HTTPException) as exc_info:
            await svc.list_slots(uuid4())
        assert exc_info.value.status_code == 404


# ==============================================================================
# Isolation multi-tenant
# ==============================================================================


class TestWheelTenantIsolation:
    async def test_tenant_isolation(self, db_session: AsyncSession) -> None:
        """Un tenant ne peut pas voir les roues d'un autre tenant."""
        tenant_a = Tenant(id=uuid4(), name="WheelTenantA")
        tenant_b = Tenant(id=uuid4(), name="WheelTenantB")
        db_session.add_all([tenant_a, tenant_b])
        await db_session.commit()

        svc_a = _svc(tenant_a.id)
        svc_b = _svc(tenant_b.id)

        await svc_a.create(_req(wheel_uid="WA-001"))
        await svc_a.create(_req(wheel_uid="WA-002"))
        await svc_b.create(_req(wheel_uid="WB-001"))

        list_a = await svc_a.list()
        list_b = await svc_b.list()

        assert len(list_a) == 2
        assert len(list_b) == 1

    async def test_get_other_tenant_wheel_returns_404(
        self,
        db_session: AsyncSession,
    ) -> None:
        """get() sur une roue d'un autre tenant lève 404."""
        tenant_a = Tenant(id=uuid4(), name="WheelCrossA")
        tenant_b = Tenant(id=uuid4(), name="WheelCrossB")
        db_session.add_all([tenant_a, tenant_b])
        await db_session.commit()

        svc_a = _svc(tenant_a.id)
        svc_b = _svc(tenant_b.id)

        wheel = await svc_a.create(_req(wheel_uid="WA-CROSS"))

        with pytest.raises(HTTPException) as exc_info:
            await svc_b.get(wheel.id)
        assert exc_info.value.status_code == 404
