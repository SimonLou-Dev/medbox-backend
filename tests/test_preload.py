"""Tests — preload_upcoming_distributions task + list_upcoming_by_box repository."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from medbox.core.db.models.box import Box
from medbox.core.db.models.prescription_schedule_item import PrescriptionScheduleItem
from medbox.core.db.models.tenant import Tenant
from medbox.core.db.repositories.prescription_schedule_item import (
    PrescriptionScheduleItemRepository,
)

pytestmark = pytest.mark.asyncio


# ==============================================================================
# Helpers
# ==============================================================================

_NOW = datetime.now(tz=UTC)
_FUTURE = _NOW + timedelta(hours=2)


async def _make_box(db_session: AsyncSession, tenant_id, status="active") -> Box:
    box = Box(
        id=uuid4(),
        tenant_id=tenant_id,
        box_uid=f"BOX-{uuid4().hex[:8]}",
        status=status,
    )
    db_session.add(box)
    await db_session.flush()
    return box


async def _make_psi(
    db_session: AsyncSession,
    tenant_id,
    box_id,
    scheduled_at=None,
    status="pending",
) -> PrescriptionScheduleItem:
    item = PrescriptionScheduleItem(
        id=uuid4(),
        tenant_id=tenant_id,
        box_id=box_id,
        scheduled_at=scheduled_at or _FUTURE,
        status=status,
    )
    db_session.add(item)
    await db_session.flush()
    return item


def _make_mqtt_mock():
    """Async context manager mock for aiomqtt.Client."""
    client = MagicMock()
    client.publish = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


# ==============================================================================
# Repository — list_upcoming_by_box
# ==============================================================================


@pytest.mark.asyncio
class TestListUpcomingByBox:
    async def test_returns_pending_future_items(self, db_session: AsyncSession):
        tenant = Tenant(id=uuid4(), name="T-LUB")
        db_session.add(tenant)
        await db_session.flush()

        box = await _make_box(db_session, tenant.id)
        await _make_psi(db_session, tenant.id, box.id, _FUTURE)
        await _make_psi(db_session, tenant.id, box.id, _FUTURE + timedelta(hours=4))
        await db_session.commit()

        repo = PrescriptionScheduleItemRepository()
        items = await repo.list_upcoming_by_box(box.id, limit=3)
        assert len(items) == 2

    async def test_limit_respected(self, db_session: AsyncSession):
        tenant = Tenant(id=uuid4(), name="T-LIM")
        db_session.add(tenant)
        await db_session.flush()

        box = await _make_box(db_session, tenant.id)
        for i in range(5):
            await _make_psi(
                db_session, tenant.id, box.id, _FUTURE + timedelta(hours=i)
            )
        await db_session.commit()

        repo = PrescriptionScheduleItemRepository()
        items = await repo.list_upcoming_by_box(box.id, limit=3)
        assert len(items) == 3

    async def test_excludes_past_items(self, db_session: AsyncSession):
        tenant = Tenant(id=uuid4(), name="T-PAST")
        db_session.add(tenant)
        await db_session.flush()

        box = await _make_box(db_session, tenant.id)
        past = _NOW - timedelta(hours=1)
        await _make_psi(db_session, tenant.id, box.id, past)  # past → excluded
        await _make_psi(db_session, tenant.id, box.id, _FUTURE)  # future → included
        await db_session.commit()

        repo = PrescriptionScheduleItemRepository()
        items = await repo.list_upcoming_by_box(box.id, limit=3)
        assert len(items) == 1
        # SQLite returns naive datetimes; just verify it's the future item
        assert items[0].scheduled_at >= _FUTURE.replace(tzinfo=None)

    async def test_excludes_non_pending_status(self, db_session: AsyncSession):
        tenant = Tenant(id=uuid4(), name="T-STATUS")
        db_session.add(tenant)
        await db_session.flush()

        box = await _make_box(db_session, tenant.id)
        await _make_psi(db_session, tenant.id, box.id, _FUTURE, status="taken")
        await _make_psi(db_session, tenant.id, box.id, _FUTURE, status="error")
        await _make_psi(db_session, tenant.id, box.id, _FUTURE, status="pending")
        await db_session.commit()

        repo = PrescriptionScheduleItemRepository()
        items = await repo.list_upcoming_by_box(box.id, limit=3)
        assert len(items) == 1
        assert items[0].status == "pending"

    async def test_ordered_by_scheduled_at(self, db_session: AsyncSession):
        tenant = Tenant(id=uuid4(), name="T-ORDER")
        db_session.add(tenant)
        await db_session.flush()

        box = await _make_box(db_session, tenant.id)
        t3 = _FUTURE + timedelta(hours=6)
        t1 = _FUTURE
        t2 = _FUTURE + timedelta(hours=3)
        await _make_psi(db_session, tenant.id, box.id, t3)
        await _make_psi(db_session, tenant.id, box.id, t1)
        await _make_psi(db_session, tenant.id, box.id, t2)
        await db_session.commit()

        repo = PrescriptionScheduleItemRepository()
        items = await repo.list_upcoming_by_box(box.id, limit=3)
        times = [i.scheduled_at for i in items]
        assert times == sorted(times)

    async def test_empty_box_returns_empty(self, db_session: AsyncSession):
        tenant = Tenant(id=uuid4(), name="T-EMPTY")
        db_session.add(tenant)
        await db_session.flush()

        box = await _make_box(db_session, tenant.id)
        await db_session.commit()

        repo = PrescriptionScheduleItemRepository()
        items = await repo.list_upcoming_by_box(box.id, limit=3)
        assert items == []


# ==============================================================================
# Task — preload_upcoming_distributions
# ==============================================================================


def _invoke_task_capture_coro():
    """Appelle le task Celery et capture la coroutine que asyncio.run() aurait exécutée."""
    from medbox.schedulerworker.tasks.preload import preload_upcoming_distributions

    captured = []

    def fake_asyncio_run(coro):
        captured.append(coro)
        return {}

    with patch("asyncio.run", fake_asyncio_run):
        preload_upcoming_distributions()

    assert captured, "asyncio.run was not called"
    return captured[0]


@pytest.mark.asyncio
class TestPreloadTask:
    async def test_no_active_boxes_returns_zeros(self, db_session: AsyncSession):
        """Aucune box active → stats vides, pas de publication MQTT."""
        mqtt_mock = _make_mqtt_mock()
        ssl_mock = MagicMock()
        ssl_mock.load_cert_chain = MagicMock()

        coro = _invoke_task_capture_coro()

        with (
            patch("aiomqtt.Client", return_value=mqtt_mock),
            patch("ssl.create_default_context", return_value=ssl_mock),
        ):
            result = await coro

        assert result["boxes_processed"] == 0
        assert result["total_items_sent"] == 0
        mqtt_mock.publish.assert_not_called()

    async def test_active_box_with_items_publishes_mqtt(self, db_session: AsyncSession):
        """Une box active avec des items pending → publie un message MQTT."""
        tenant = Tenant(id=uuid4(), name="T-PRELOAD")
        db_session.add(tenant)
        await db_session.flush()

        box = await _make_box(db_session, tenant.id, status="active")
        await _make_psi(db_session, tenant.id, box.id, _FUTURE)
        await _make_psi(db_session, tenant.id, box.id, _FUTURE + timedelta(hours=4))
        await db_session.commit()

        mqtt_mock = _make_mqtt_mock()
        ssl_mock = MagicMock()
        ssl_mock.load_cert_chain = MagicMock()

        coro = _invoke_task_capture_coro()

        with (
            patch("aiomqtt.Client", return_value=mqtt_mock),
            patch("ssl.create_default_context", return_value=ssl_mock),
        ):
            result = await coro

        assert result["boxes_processed"] >= 1
        assert result["total_items_sent"] >= 2
        mqtt_mock.publish.assert_called()

        # Vérifier le topic et le payload
        call_args = mqtt_mock.publish.call_args
        topic = call_args[0][0]
        assert box.box_uid in topic
        assert "cmd/preload" in topic

        payload_str = call_args[1]["payload"]
        payload = json.loads(payload_str)
        assert "distributions" in payload
        assert len(payload["distributions"]) == 2

    async def test_limit_3_items_per_box(self, db_session: AsyncSession):
        """Même avec 5 items pending, seulement 3 sont envoyés."""
        tenant = Tenant(id=uuid4(), name="T-LIMIT")
        db_session.add(tenant)
        await db_session.flush()

        box = await _make_box(db_session, tenant.id, status="active")
        for i in range(5):
            await _make_psi(
                db_session, tenant.id, box.id, _FUTURE + timedelta(hours=i)
            )
        await db_session.commit()

        mqtt_mock = _make_mqtt_mock()
        ssl_mock = MagicMock()
        ssl_mock.load_cert_chain = MagicMock()

        coro = _invoke_task_capture_coro()

        with (
            patch("aiomqtt.Client", return_value=mqtt_mock),
            patch("ssl.create_default_context", return_value=ssl_mock),
        ):
            result = await coro

        payload_str = mqtt_mock.publish.call_args[1]["payload"]
        payload = json.loads(payload_str)
        assert len(payload["distributions"]) == 3
        assert result["total_items_sent"] == 3

    async def test_inactive_box_not_processed(self, db_session: AsyncSession):
        """Une box inactive ne reçoit pas de preload."""
        tenant = Tenant(id=uuid4(), name="T-INACTIVE")
        db_session.add(tenant)
        await db_session.flush()

        box = await _make_box(db_session, tenant.id, status="inactive")
        await _make_psi(db_session, tenant.id, box.id, _FUTURE)
        await db_session.commit()

        mqtt_mock = _make_mqtt_mock()
        ssl_mock = MagicMock()

        coro = _invoke_task_capture_coro()

        with (
            patch("aiomqtt.Client", return_value=mqtt_mock),
            patch("ssl.create_default_context", return_value=ssl_mock),
        ):
            result = await coro

        mqtt_mock.publish.assert_not_called()
        assert result["boxes_processed"] == 0

    async def test_box_without_upcoming_items_is_skipped(
        self, db_session: AsyncSession
    ):
        """Box active sans item pending → comptée dans boxes_skipped."""
        tenant = Tenant(id=uuid4(), name="T-SKIP")
        db_session.add(tenant)
        await db_session.flush()

        await _make_box(db_session, tenant.id, status="active")
        # Pas de PSI → rien à envoyer
        await db_session.commit()

        mqtt_mock = _make_mqtt_mock()
        ssl_mock = MagicMock()

        coro = _invoke_task_capture_coro()

        with (
            patch("aiomqtt.Client", return_value=mqtt_mock),
            patch("ssl.create_default_context", return_value=ssl_mock),
        ):
            result = await coro

        mqtt_mock.publish.assert_not_called()
        assert result["boxes_skipped"] >= 1

    async def test_mqtt_error_skips_box_continues(self, db_session: AsyncSession):
        """Une erreur MQTT pour une box ne plante pas le job global."""
        tenant = Tenant(id=uuid4(), name="T-MQTTERR")
        db_session.add(tenant)
        await db_session.flush()

        box = await _make_box(db_session, tenant.id, status="active")
        await _make_psi(db_session, tenant.id, box.id, _FUTURE)
        await db_session.commit()

        mqtt_mock = _make_mqtt_mock()
        mqtt_mock.publish = AsyncMock(side_effect=ConnectionError("MQTT down"))
        ssl_mock = MagicMock()

        coro = _invoke_task_capture_coro()

        with (
            patch("aiomqtt.Client", return_value=mqtt_mock),
            patch("ssl.create_default_context", return_value=ssl_mock),
        ):
            result = await coro

        assert result["boxes_skipped"] >= 1
        assert result["boxes_processed"] == 0

    async def test_payload_contains_scheduled_at_iso(self, db_session: AsyncSession):
        """Le payload MQTT contient scheduled_at en ISO 8601."""
        tenant = Tenant(id=uuid4(), name="T-ISO")
        db_session.add(tenant)
        await db_session.flush()

        box = await _make_box(db_session, tenant.id, status="active")
        await _make_psi(db_session, tenant.id, box.id, _FUTURE)
        await db_session.commit()

        mqtt_mock = _make_mqtt_mock()
        ssl_mock = MagicMock()

        coro = _invoke_task_capture_coro()

        with (
            patch("aiomqtt.Client", return_value=mqtt_mock),
            patch("ssl.create_default_context", return_value=ssl_mock),
        ):
            await coro

        payload_str = mqtt_mock.publish.call_args[1]["payload"]
        payload = json.loads(payload_str)
        dist = payload["distributions"][0]
        assert "scheduled_at" in dist
        assert "schedule_item_id" in dist
        # Vérifie le format ISO 8601 (T comme séparateur date/heure)
        assert "T" in dist["scheduled_at"]
