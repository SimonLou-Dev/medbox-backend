"""Tests d'intégration — WheelLoadPlanService (moulinette + confirm)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from medbox.core.db.models.box import Box
from medbox.core.db.models.patient import Patient
from medbox.core.db.models.prescription import Prescription
from medbox.core.db.models.prescription_item import PrescriptionItem
from medbox.core.db.models.tenant import Tenant
from medbox.core.db.models.wheel import Wheel
from medbox.core.dto.wheel_load_plan import WheelLoadPlanConfirmRequest, WheelLoadPlanCreateRequest
from medbox.core.services.wheel_load_plan import (
    WheelLoadPlanService,
    _resolve_distribution_times,
)

_NOW = datetime(2026, 6, 12, 8, 0, 0, tzinfo=UTC)


# ==============================================================================
# Helpers
# ==============================================================================


async def _setup_base(db_session: AsyncSession):
    """Crée tenant, patient, box, wheel et une prescription active."""
    tenant = Tenant(id=uuid4(), name=f"T-{uuid4().hex[:6]}")
    db_session.add(tenant)
    await db_session.flush()

    patient = Patient(
        id=uuid4(),
        tenant_id=tenant.id,
        c_first_name="Alice",
        c_last_name="Dupont",
    )
    db_session.add(patient)

    box = Box(
        id=uuid4(),
        tenant_id=tenant.id,
        box_uid=f"BOX-{uuid4().hex[:8]}",
        status="active",
    )
    db_session.add(box)

    wheel = Wheel(
        id=uuid4(),
        tenant_id=tenant.id,
        wheel_uid=f"WHL-{uuid4().hex[:8]}",
        slot_count=22,
        status="in_stock",
    )
    db_session.add(wheel)
    await db_session.flush()

    # Prescription active avec un item 1x/jour (matin)
    presc = Prescription(
        id=uuid4(),
        tenant_id=tenant.id,
        patient_id=patient.id,
        status="active",
    )
    db_session.add(presc)
    await db_session.flush()

    item = PrescriptionItem(
        id=uuid4(),
        prescription_id=presc.id,
        medication_label="DOLIPRANE 500mg",
        dose={"value": 500, "unit": "mg"},
        frequency={"times_per_day": 1, "moments": ["matin"], "pattern": "1x/jour"},
    )
    db_session.add(item)
    await db_session.commit()

    return tenant, patient, box, wheel, presc, item


def _svc(tenant_id) -> WheelLoadPlanService:
    return WheelLoadPlanService(tenant_id=tenant_id)


def _create_req(wheel_id, box_id, prescription_ids, valid_from=None):
    return WheelLoadPlanCreateRequest(
        wheel_id=wheel_id,
        box_id=box_id,
        prescription_ids=prescription_ids,
        valid_from=valid_from or _NOW,
    )


# ==============================================================================
# Résolution des horaires
# ==============================================================================


class TestResolveDistributionTimes:
    def test_moments_matin(self):
        from datetime import time

        times = _resolve_distribution_times({"moments": ["matin"]})
        assert times == [time(8, 0)]

    def test_moments_multiple(self):
        from datetime import time

        times = _resolve_distribution_times({"moments": ["matin", "soir"]})
        assert time(8, 0) in times
        assert time(19, 0) in times
        assert len(times) == 2

    def test_times_per_day_3(self):
        from datetime import time

        times = _resolve_distribution_times({"times_per_day": 3})
        assert len(times) == 3
        assert time(8, 0) in times

    def test_fallback_default(self):
        from datetime import time

        times = _resolve_distribution_times({})
        assert times == [time(8, 0)]

    def test_unknown_moment_falls_back_to_frequency(self):
        from datetime import time

        times = _resolve_distribution_times({"moments": ["inconnu"], "times_per_day": 2})
        assert len(times) == 2


# ==============================================================================
# Moulinette — création du plan
# ==============================================================================


@pytest.mark.asyncio
class TestWheelLoadPlanCreate:
    async def test_creates_plan_with_filling_list(self, db_session: AsyncSession):
        tenant, _, box, wheel, presc, _ = await _setup_base(db_session)
        svc = _svc(tenant.id)

        result = await svc.create(
            _create_req(wheel.id, box.id, [presc.id]),
            created_by_user_id=uuid4(),
        )

        assert result.id is not None
        assert result.status == "draft"
        assert result.total_slots_used == 21
        assert result.days_covered == 21
        assert len(result.filling_list) == 21
        # Case 1 = index 0
        assert result.filling_list[0].case_number == 1
        assert result.filling_list[0].slot_index == 0
        assert len(result.filling_list[0].medications) == 1
        assert result.filling_list[0].medications[0].medication_label == "DOLIPRANE 500mg"

    async def test_two_items_twice_per_day_covers_10_days(self, db_session: AsyncSession):
        """2 prises/jour → 21//2 = 10 jours couverts, 20 slots utilisés."""
        tenant, patient, box, wheel, _, _ = await _setup_base(db_session)

        presc2 = Prescription(
            id=uuid4(), tenant_id=tenant.id, patient_id=patient.id, status="active"
        )
        db_session.add(presc2)
        await db_session.flush()

        item2 = PrescriptionItem(
            id=uuid4(),
            prescription_id=presc2.id,
            medication_label="IBUPROFEN 400mg",
            frequency={"times_per_day": 2, "moments": ["matin", "soir"]},
        )
        db_session.add(item2)
        await db_session.commit()

        svc = _svc(tenant.id)
        result = await svc.create(
            _create_req(wheel.id, box.id, [presc2.id]),
            created_by_user_id=uuid4(),
        )

        assert result.days_covered == 10
        assert result.total_slots_used == 20
        assert len(result.filling_list) == 20

    async def test_wheel_not_found_raises_404(self, db_session: AsyncSession):
        tenant, _, box, _, presc, _ = await _setup_base(db_session)
        svc = _svc(tenant.id)

        with pytest.raises(HTTPException) as exc_info:
            await svc.create(_create_req(uuid4(), box.id, [presc.id]), uuid4())
        assert exc_info.value.status_code == 404

    async def test_prescription_not_found_raises_404(self, db_session: AsyncSession):
        tenant, _, box, wheel, _, _ = await _setup_base(db_session)
        svc = _svc(tenant.id)

        with pytest.raises(HTTPException) as exc_info:
            await svc.create(_create_req(wheel.id, box.id, [uuid4()]), uuid4())
        assert exc_info.value.status_code == 404

    async def test_inactive_prescription_raises_404(self, db_session: AsyncSession):
        tenant, patient, box, wheel, _, _ = await _setup_base(db_session)

        inactive = Prescription(
            id=uuid4(), tenant_id=tenant.id, patient_id=patient.id, status="stopped"
        )
        db_session.add(inactive)
        await db_session.commit()

        svc = _svc(tenant.id)
        with pytest.raises(HTTPException) as exc_info:
            await svc.create(_create_req(wheel.id, box.id, [inactive.id]), uuid4())
        assert exc_info.value.status_code == 404

    async def test_wheel_wrong_status_raises_409(self, db_session: AsyncSession):
        tenant, _, box, _, presc, _ = await _setup_base(db_session)

        mounted_wheel = Wheel(
            id=uuid4(),
            tenant_id=tenant.id,
            wheel_uid=f"WHL-MTD-{uuid4().hex[:6]}",
            slot_count=22,
            status="mounted",
        )
        db_session.add(mounted_wheel)
        await db_session.commit()

        svc = _svc(tenant.id)
        with pytest.raises(HTTPException) as exc_info:
            await svc.create(_create_req(mounted_wheel.id, box.id, [presc.id]), uuid4())
        assert exc_info.value.status_code == 409

    async def test_filling_list_day_offset(self, db_session: AsyncSession):
        """Les slots du jour 2 ont day_offset=1."""
        tenant, patient, box, wheel, _, _ = await _setup_base(db_session)

        presc = Prescription(
            id=uuid4(), tenant_id=tenant.id, patient_id=patient.id, status="active"
        )
        db_session.add(presc)
        await db_session.flush()

        item = PrescriptionItem(
            id=uuid4(),
            prescription_id=presc.id,
            medication_label="MED-X",
            frequency={"times_per_day": 1, "moments": ["matin"]},
        )
        db_session.add(item)
        await db_session.commit()

        svc = _svc(tenant.id)
        result = await svc.create(_create_req(wheel.id, box.id, [presc.id]), uuid4())

        assert result.filling_list[0].day_offset == 0
        assert result.filling_list[1].day_offset == 1
        assert result.filling_list[20].day_offset == 20


# ==============================================================================
# Confirm — création des PrescriptionScheduleItems
# ==============================================================================


@pytest.mark.asyncio
class TestWheelLoadPlanConfirm:
    async def _create_plan(self, db_session, tenant, box, wheel, presc):
        svc = _svc(tenant.id)
        return await svc.create(
            _create_req(wheel.id, box.id, [presc.id]),
            created_by_user_id=uuid4(),
        )

    async def test_confirm_creates_schedule_items(self, db_session: AsyncSession):
        tenant, _, box, wheel, presc, _ = await _setup_base(db_session)
        plan = await self._create_plan(db_session, tenant, box, wheel, presc)

        svc = _svc(tenant.id)
        with patch(
            "medbox.api.ws.manager.publish_to_user",
            new=AsyncMock(),
        ):
            result = await svc.confirm(
                plan.id,
                WheelLoadPlanConfirmRequest(box_id=box.id),
                user_id=uuid4(),
            )

        assert result.status == "active"
        assert result.confirmed_at is not None
        assert result.total_slots_used == 21

    async def test_confirm_sets_wheel_status_mounted(self, db_session: AsyncSession):
        from sqlalchemy import select

        tenant, _, box, wheel, presc, _ = await _setup_base(db_session)
        plan = await self._create_plan(db_session, tenant, box, wheel, presc)

        svc = _svc(tenant.id)
        with patch(
            "medbox.api.ws.manager.publish_to_user",
            new=AsyncMock(),
        ):
            await svc.confirm(
                plan.id,
                WheelLoadPlanConfirmRequest(box_id=box.id),
                user_id=uuid4(),
            )

        from medbox.core.db.session import async_session_local

        async with async_session_local() as session:
            result = await session.execute(select(Wheel).where(Wheel.id == wheel.id))
            updated_wheel = result.scalar_one()
        assert updated_wheel.status == "mounted"

    async def test_confirm_already_active_raises_409(self, db_session: AsyncSession):
        tenant, _, box, wheel, presc, _ = await _setup_base(db_session)
        plan = await self._create_plan(db_session, tenant, box, wheel, presc)

        svc = _svc(tenant.id)
        with patch(
            "medbox.api.ws.manager.publish_to_user",
            new=AsyncMock(),
        ):
            await svc.confirm(
                plan.id,
                WheelLoadPlanConfirmRequest(box_id=box.id),
                user_id=uuid4(),
            )

            with pytest.raises(HTTPException) as exc_info:
                await svc.confirm(
                    plan.id,
                    WheelLoadPlanConfirmRequest(box_id=box.id),
                    user_id=uuid4(),
                )
        assert exc_info.value.status_code == 409

    async def test_confirm_unknown_plan_raises_404(self, db_session: AsyncSession):
        tenant, _, box, _, _, _ = await _setup_base(db_session)
        svc = _svc(tenant.id)

        with pytest.raises(HTTPException) as exc_info:
            await svc.confirm(
                uuid4(),
                WheelLoadPlanConfirmRequest(box_id=box.id),
                user_id=uuid4(),
            )
        assert exc_info.value.status_code == 404

    async def test_confirm_ws_failure_is_non_blocking(self, db_session: AsyncSession):
        """Une erreur WS ne doit pas faire échouer la confirmation."""
        tenant, _, box, wheel, presc, _ = await _setup_base(db_session)
        plan = await self._create_plan(db_session, tenant, box, wheel, presc)

        svc = _svc(tenant.id)
        with patch(
            "medbox.api.ws.manager.publish_to_user",
            new=AsyncMock(side_effect=ConnectionError("redis down")),
        ):
            result = await svc.confirm(
                plan.id,
                WheelLoadPlanConfirmRequest(box_id=box.id),
                user_id=uuid4(),
            )

        assert result.status == "active"


# ==============================================================================
# List
# ==============================================================================


@pytest.mark.asyncio
class TestWheelLoadPlanList:
    async def test_list_empty(self, db_session: AsyncSession):
        tenant = Tenant(id=uuid4(), name="T-LIST")
        db_session.add(tenant)
        await db_session.commit()

        svc = _svc(tenant.id)
        result = await svc.list()
        assert result == []

    async def test_list_returns_tenant_plans(self, db_session: AsyncSession):
        tenant, _, box, wheel, presc, _ = await _setup_base(db_session)
        svc = _svc(tenant.id)

        await svc.create(_create_req(wheel.id, box.id, [presc.id]), uuid4())
        result = await svc.list()
        assert len(result) == 1
        assert result[0].tenant_id == tenant.id

    async def test_list_tenant_isolation(self, db_session: AsyncSession):
        tenant_a, _, box_a, wheel_a, presc_a, _ = await _setup_base(db_session)
        tenant_b, _, box_b, wheel_b, presc_b, _ = await _setup_base(db_session)

        svc_a = _svc(tenant_a.id)
        svc_b = _svc(tenant_b.id)

        await svc_a.create(_create_req(wheel_a.id, box_a.id, [presc_a.id]), uuid4())

        assert len(await svc_a.list()) == 1
        assert len(await svc_b.list()) == 0
