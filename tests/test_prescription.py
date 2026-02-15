"""Integration tests for PrescriptionService with real database."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from medbox.core.db.models.patient import Patient
from medbox.core.db.models.tenant import Tenant
from medbox.core.dto.prescription import (
    DoseSchema,
    FrequencySchema,
    PrescriptionItemRequest,
    PrescriptionRequest,
    StatusUpdateRequest,
)
from medbox.core.services.prescription import PrescriptionService

pytestmark = pytest.mark.asyncio


# ==============================================================================
# Helpers
# ==============================================================================


async def _setup_tenant_patient(db_session: AsyncSession):
    """Create a tenant and patient for tests."""
    tenant = Tenant(id=uuid4(), name="Test Tenant")
    db_session.add(tenant)
    await db_session.commit()

    patient = Patient(
        id=uuid4(),
        tenant_id=tenant.id,
        c_first_name="John",
        c_last_name="Doe",
    )
    db_session.add(patient)
    await db_session.commit()

    return tenant, patient


def _make_svc(tenant_id):
    """Create a PrescriptionService with mocked S3 client."""
    return PrescriptionService(tenant_id=tenant_id, s3_client=AsyncMock())


def _item(
    label: str = "DOLIPRANE 500mg",
    dose_value: float | None = 500,
    dose_unit: str = "mg",
    pattern: str = "3x/jour",
    times_per_day: int | None = 3,
):
    """Shorthand to create an item request."""
    return PrescriptionItemRequest(
        medication_cis=None,
        medication_label=label,
        dose=DoseSchema(value=dose_value, unit=dose_unit) if dose_value else None,
        frequency=FrequencySchema(
            pattern=pattern,
            times_per_day=times_per_day,
        ),
    )


def _req(patient_id, **kwargs):
    """Shorthand to create a PrescriptionRequest with defaults."""
    defaults = {
        "patient_id": patient_id,
        "c_notes": None,
        "start_date": None,
        "end_date": None,
        "items": [_item()],
    }
    defaults.update(kwargs)
    return PrescriptionRequest(**defaults)


# ==============================================================================
# Prescription CRUD
# ==============================================================================


class TestPrescriptionCRUD:
    """Tests for prescription CRUD operations."""

    async def test_create_and_get(self, db_session: AsyncSession) -> None:
        tenant, patient = await _setup_tenant_patient(db_session)
        svc = _make_svc(tenant.id)

        created = await svc.create(_req(
            patient.id,
            title="Ordonnance 1",
            status="active",
        ))

        assert created.title == "Ordonnance 1"
        assert created.status == "active"
        assert created.patient_id == patient.id
        assert len(created.items) == 1
        assert created.items[0].medication_label == "DOLIPRANE 500mg"
        assert created.items[0].dose.value == 500
        assert created.items[0].dose.unit == "mg"
        assert created.items[0].frequency.pattern == "3x/jour"
        assert created.items[0].frequency.times_per_day == 3

        # Retrieve
        retrieved = await svc.get(created.id)
        assert retrieved.id == created.id
        assert len(retrieved.items) == 1

    async def test_create_multiple_items(self, db_session: AsyncSession) -> None:
        tenant, patient = await _setup_tenant_patient(db_session)
        svc = _make_svc(tenant.id)

        created = await svc.create(_req(
            patient.id,
            items=[
                _item("Med A", 100, "mg", "1x/jour", 1),
                _item("Med B", None, "mg", "si besoin", None),
                _item("Med C", 1, "cp", "matin+soir", 2),
            ],
        ))

        assert len(created.items) == 3
        labels = {i.medication_label for i in created.items}
        assert labels == {"Med A", "Med B", "Med C"}

        # dose can be None
        med_b = next(i for i in created.items if i.medication_label == "Med B")
        assert med_b.dose is None

    async def test_create_patient_not_found(self, db_session: AsyncSession) -> None:
        tenant, _ = await _setup_tenant_patient(db_session)
        svc = _make_svc(tenant.id)

        with pytest.raises(HTTPException) as exc_info:
            await svc.create(_req(uuid4()))
        assert exc_info.value.status_code == 404

    async def test_list_by_patient(self, db_session: AsyncSession) -> None:
        tenant, patient = await _setup_tenant_patient(db_session)
        svc = _make_svc(tenant.id)

        for i in range(3):
            await svc.create(_req(patient.id, title=f"Rx {i}"))

        result = await svc.list_by_patient(patient_id=patient.id)
        assert result["total"] == 3
        assert len(result["items"]) == 3

    async def test_list_by_patient_status_filter(self, db_session: AsyncSession) -> None:
        tenant, patient = await _setup_tenant_patient(db_session)
        svc = _make_svc(tenant.id)

        # 2 active, 1 paused
        for _ in range(2):
            await svc.create(_req(patient.id, status="active"))
        await svc.create(_req(patient.id, status="paused"))

        active = await svc.list_by_patient(patient_id=patient.id, status="active")
        assert active["total"] == 2

        paused = await svc.list_by_patient(patient_id=patient.id, status="paused")
        assert paused["total"] == 1

    async def test_update(self, db_session: AsyncSession) -> None:
        tenant, patient = await _setup_tenant_patient(db_session)
        svc = _make_svc(tenant.id)

        created = await svc.create(_req(patient.id, title="Original"))

        updated = await svc.update(
            created.id,
            _req(
                patient.id,
                title="Updated",
                status="paused",
                items=[_item("Med 2", 200, "mg"), _item("Med 3")],
            ),
        )

        assert updated.title == "Updated"
        assert updated.status == "paused"
        assert len(updated.items) == 2

    async def test_update_status(self, db_session: AsyncSession) -> None:
        tenant, patient = await _setup_tenant_patient(db_session)
        svc = _make_svc(tenant.id)

        created = await svc.create(_req(patient.id, title="Test"))

        updated = await svc.update_status(created.id, StatusUpdateRequest(status="stopped"))
        assert updated.status == "stopped"
        assert updated.title == "Test"  # rest unchanged

    async def test_delete(self, db_session: AsyncSession) -> None:
        tenant, patient = await _setup_tenant_patient(db_session)
        svc = _make_svc(tenant.id)

        created = await svc.create(_req(patient.id))
        pid = created.id

        assert await svc.delete(pid) is True

        with pytest.raises(HTTPException) as exc_info:
            await svc.get(pid)
        assert exc_info.value.status_code == 404

    async def test_tenant_isolation(self, db_session: AsyncSession) -> None:
        # Two tenants
        t1 = Tenant(id=uuid4(), name="T1")
        t2 = Tenant(id=uuid4(), name="T2")
        db_session.add_all([t1, t2])
        await db_session.commit()

        p1 = Patient(id=uuid4(), tenant_id=t1.id, c_first_name="A", c_last_name="B")
        db_session.add(p1)
        await db_session.commit()

        svc1 = _make_svc(t1.id)
        svc2 = _make_svc(t2.id)

        rx = await svc1.create(_req(p1.id))

        # tenant 2 cannot access
        with pytest.raises(HTTPException) as exc_info:
            await svc2.get(rx.id)
        assert exc_info.value.status_code == 404


# ==============================================================================
# Item Management
# ==============================================================================


class TestItemManagement:
    """Tests for individual item operations."""

    async def test_add_item(self, db_session: AsyncSession) -> None:
        tenant, patient = await _setup_tenant_patient(db_session)
        svc = _make_svc(tenant.id)

        rx = await svc.create(_req(patient.id, items=[_item("Med 1")]))
        assert len(rx.items) == 1

        updated = await svc.add_item(rx.id, _item("Med 2", 100, "mg", "2x/jour", 2))
        assert len(updated.items) == 2

    async def test_update_item(self, db_session: AsyncSession) -> None:
        tenant, patient = await _setup_tenant_patient(db_session)
        svc = _make_svc(tenant.id)

        rx = await svc.create(_req(patient.id, items=[_item("Original")]))
        item_id = rx.items[0].id

        updated = await svc.update_item(
            rx.id,
            item_id,
            _item("Updated", 999, "mg", "5x/jour", 5),
        )
        assert updated.items[0].medication_label == "Updated"
        assert updated.items[0].dose.value == 999
        assert updated.items[0].frequency.pattern == "5x/jour"

    async def test_delete_item(self, db_session: AsyncSession) -> None:
        tenant, patient = await _setup_tenant_patient(db_session)
        svc = _make_svc(tenant.id)

        rx = await svc.create(_req(
            patient.id,
            items=[_item("Med 1"), _item("Med 2")],
        ))
        item_to_delete = rx.items[0].id

        updated = await svc.delete_item(rx.id, item_to_delete)
        assert len(updated.items) == 1

    async def test_delete_last_item_fails(self, db_session: AsyncSession) -> None:
        tenant, patient = await _setup_tenant_patient(db_session)
        svc = _make_svc(tenant.id)

        rx = await svc.create(_req(patient.id))
        item_id = rx.items[0].id

        with pytest.raises(HTTPException) as exc_info:
            await svc.delete_item(rx.id, item_id)
        assert exc_info.value.status_code == 400

    async def test_get_item(self, db_session: AsyncSession) -> None:
        tenant, patient = await _setup_tenant_patient(db_session)
        svc = _make_svc(tenant.id)

        rx = await svc.create(_req(
            patient.id,
            items=[_item("Med A"), _item("Med B")],
        ))
        item_id = rx.items[1].id

        item = await svc.get_item(rx.id, item_id)
        assert item.id == item_id

    async def test_item_not_found(self, db_session: AsyncSession) -> None:
        tenant, patient = await _setup_tenant_patient(db_session)
        svc = _make_svc(tenant.id)

        rx = await svc.create(_req(patient.id))

        with pytest.raises(HTTPException) as exc_info:
            await svc.get_item(rx.id, uuid4())
        assert exc_info.value.status_code == 404


# ==============================================================================
# Document Handling (S3 mocked)
# ==============================================================================


class TestDocumentHandling:
    """Tests for document upload/download with mocked S3."""

    async def test_upload_document(self, db_session: AsyncSession) -> None:
        tenant, patient = await _setup_tenant_patient(db_session)
        mock_s3 = AsyncMock()
        mock_s3.upload_file.return_value = "test-key"
        mock_s3.build_s3_key = MagicMock(return_value="tenant/prescriptions/rx/ordonnance.pdf")
        svc = PrescriptionService(tenant_id=tenant.id, s3_client=mock_s3)

        rx = await svc.create(_req(patient.id))

        mock_file = AsyncMock()
        mock_file.filename = "ordonnance.pdf"
        mock_file.content_type = "application/pdf"
        mock_file.read = AsyncMock(return_value=b"fake pdf content")

        updated = await svc.upload_document(rx.id, mock_file)
        assert updated.has_document is True
        assert updated.document_file_name == "ordonnance.pdf"
        mock_s3.upload_file.assert_called_once()

    async def test_get_document_url(self, db_session: AsyncSession) -> None:
        tenant, patient = await _setup_tenant_patient(db_session)
        mock_s3 = AsyncMock()
        mock_s3.upload_file.return_value = "test-key"
        mock_s3.build_s3_key = MagicMock(return_value="tenant/prescriptions/rx/ordonnance.pdf")
        mock_s3.generate_presigned_url.return_value = "https://s3.example.com/presigned"
        svc = PrescriptionService(tenant_id=tenant.id, s3_client=mock_s3)

        rx = await svc.create(_req(patient.id))

        # Upload first
        mock_file = AsyncMock()
        mock_file.filename = "test.pdf"
        mock_file.content_type = "application/pdf"
        mock_file.read = AsyncMock(return_value=b"content")
        await svc.upload_document(rx.id, mock_file)

        url = await svc.get_document_url(rx.id)
        assert url == "https://s3.example.com/presigned"
        mock_s3.generate_presigned_url.assert_called_once()

    async def test_delete_document(self, db_session: AsyncSession) -> None:
        tenant, patient = await _setup_tenant_patient(db_session)
        mock_s3 = AsyncMock()
        mock_s3.upload_file.return_value = "test-key"
        mock_s3.build_s3_key = MagicMock(return_value="tenant/prescriptions/rx/ordonnance.pdf")
        mock_s3.delete_file.return_value = True
        svc = PrescriptionService(tenant_id=tenant.id, s3_client=mock_s3)

        rx = await svc.create(_req(patient.id))

        # Upload first
        mock_file = AsyncMock()
        mock_file.filename = "test.pdf"
        mock_file.content_type = "application/pdf"
        mock_file.read = AsyncMock(return_value=b"content")
        await svc.upload_document(rx.id, mock_file)

        result = await svc.delete_document(rx.id)
        assert result is True
        mock_s3.delete_file.assert_called_once()

    async def test_get_document_url_no_document(self, db_session: AsyncSession) -> None:
        tenant, patient = await _setup_tenant_patient(db_session)
        svc = _make_svc(tenant.id)

        rx = await svc.create(_req(patient.id))

        with pytest.raises(HTTPException) as exc_info:
            await svc.get_document_url(rx.id)
        assert exc_info.value.status_code == 404

    async def test_upload_invalid_type(self, db_session: AsyncSession) -> None:
        tenant, patient = await _setup_tenant_patient(db_session)
        svc = _make_svc(tenant.id)

        rx = await svc.create(_req(patient.id))

        mock_file = AsyncMock()
        mock_file.filename = "malware.exe"
        mock_file.content_type = "application/octet-stream"
        mock_file.read = AsyncMock(return_value=b"bad")

        with pytest.raises(HTTPException) as exc_info:
            await svc.upload_document(rx.id, mock_file)
        assert exc_info.value.status_code == 400
