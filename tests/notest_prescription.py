"""Integration tests for PrescriptionService with real database."""

from unittest.mock import AsyncMock
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


class TestPrescriptionServiceIntegration:
    """Integration tests for PrescriptionService with database."""

    async def test_create_and_get_prescription(self, db_session: AsyncSession) -> None:
        """Test creating and retrieving a prescription."""
        # Setup tenant and patient
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

        # Create service
        service = PrescriptionService(tenant_id=tenant.id)

        # Create prescription with items
        request = PrescriptionRequest(
            patient_id=patient.id,
            title="Test Prescription",
            status="active",
            items=[
                PrescriptionItemRequest(
                    medication_cis=12345678,
                    medication_label="DOLIPRANE 500mg",
                    dose=DoseSchema(value=500, unit="mg"),
                    frequency=FrequencySchema(
                        times_per_day=3,
                        moments=["matin", "midi", "soir"],
                        pattern="3x/jour",
                    ),
                ),
            ],
        )

        created = await service.create(request)

        assert created.title == "Test Prescription"
        assert created.status == "active"
        assert created.patient_id == patient.id
        assert created.tenant_id == tenant.id
        assert len(created.items) == 1
        assert created.items[0].medication_label == "DOLIPRANE 500mg"
        assert created.items[0].dose.value == 500
        assert created.items[0].dose.unit == "mg"
        assert created.items[0].frequency.times_per_day == 3

        # Get prescription
        retrieved = await service.get(created.id)

        assert retrieved.id == created.id
        assert retrieved.title == "Test Prescription"
        assert len(retrieved.items) == 1

    async def test_create_prescription_with_multiple_items(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test creating prescription with multiple items."""
        # Setup
        tenant = Tenant(id=uuid4(), name="Test Tenant")
        db_session.add(tenant)
        await db_session.commit()

        patient = Patient(
            id=uuid4(),
            tenant_id=tenant.id,
            c_first_name="Jane",
            c_last_name="Smith",
        )
        db_session.add(patient)
        await db_session.commit()

        service = PrescriptionService(tenant_id=tenant.id)

        # Create with 3 items
        request = PrescriptionRequest(
            patient_id=patient.id,
            title="Multi-medication",
            status="active",
            items=[
                PrescriptionItemRequest(
                    medication_label="Med 1",
                    medication_cis=None,
                    dose=DoseSchema(value=100, unit="mg"),
                    frequency=FrequencySchema(pattern="1x/jour", times_per_day=1),
                ),
                PrescriptionItemRequest(
                    medication_label="Med 2",
                    medication_cis=None,
                    dose=DoseSchema(value=50, unit="mg"),
                    frequency=FrequencySchema(pattern="2x/jour", times_per_day=2),
                ),
                PrescriptionItemRequest(
                    medication_label="Med 3",
                    medication_cis=None,
                    dose=None,
                    frequency=FrequencySchema(pattern="si besoin"),
                ),
            ],
        )

        created = await service.create(request)

        assert len(created.items) == 3
        # Verify dose can be None
        med3 = next(i for i in created.items if i.medication_label == "Med 3")
        assert med3.dose is None

    async def test_create_prescription_patient_not_found(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test creating prescription for non-existent patient."""
        tenant = Tenant(id=uuid4(), name="Test Tenant")
        db_session.add(tenant)
        await db_session.commit()

        service = PrescriptionService(tenant_id=tenant.id)

        request = PrescriptionRequest(
            patient_id=uuid4(),  # Non-existent
            items=[
                PrescriptionItemRequest(
                    medication_label="Test",
                    medication_cis=None,
                    dose=None,
                    frequency=FrequencySchema(pattern="1x/jour"),
                ),
            ],
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.create(request)

        assert exc_info.value.status_code == 404

    async def test_list_by_patient(self, db_session: AsyncSession) -> None:
        """Test listing prescriptions by patient."""
        # Setup
        tenant = Tenant(id=uuid4(), name="Test Tenant")
        db_session.add(tenant)
        await db_session.commit()

        patient = Patient(
            id=uuid4(),
            tenant_id=tenant.id,
            c_first_name="Test",
            c_last_name="Patient",
        )
        db_session.add(patient)
        await db_session.commit()

        service = PrescriptionService(tenant_id=tenant.id)

        # Create 3 prescriptions
        for i in range(3):
            request = PrescriptionRequest(
                patient_id=patient.id,
                title=f"Prescription {i+1}",
                status="active",
                items=[
                    PrescriptionItemRequest(
                        medication_label=f"Med {i+1}",
                        medication_cis=None,
                        dose=None,
                        frequency=FrequencySchema(pattern="1x/jour"),
                    ),
                ],
            )
            await service.create(request)

        # List prescriptions
        result = await service.list_by_patient(
            patient_id=patient.id,
            page=1,
            per_page=20,
        )

        assert result["pagination"]["total"] == 3
        assert len(result["data"]) == 3

    async def test_list_by_patient_with_status_filter(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test filtering prescriptions by status."""
        # Setup
        tenant = Tenant(id=uuid4(), name="Test Tenant")
        db_session.add(tenant)
        await db_session.commit()

        patient = Patient(
            id=uuid4(),
            tenant_id=tenant.id,
            c_first_name="Test",
            c_last_name="Patient",
        )
        db_session.add(patient)
        await db_session.commit()

        service = PrescriptionService(tenant_id=tenant.id)

        # Create 2 active, 1 paused
        for _ in range(2):
            request = PrescriptionRequest(
                patient_id=patient.id,
                status="active",
                items=[
                    PrescriptionItemRequest(
                        medication_label="Med",
                        medication_cis=None,
                        dose=None,
                        frequency=FrequencySchema(pattern="1x/jour"),
                    ),
                ],
            )
            await service.create(request)

        request_paused = PrescriptionRequest(
            patient_id=patient.id,
            status="paused",
            items=[
                PrescriptionItemRequest(
                    medication_label="Med",
                    medication_cis=None,
                    dose=None,
                    frequency=FrequencySchema(pattern="1x/jour"),
                ),
            ],
        )
        await service.create(request_paused)

        # Filter by active
        result = await service.list_by_patient(
            patient_id=patient.id,
            status="active",
            page=1,
            per_page=20,
        )

        assert result["pagination"]["total"] == 2

        # Filter by paused
        result_paused = await service.list_by_patient(
            patient_id=patient.id,
            status="paused",
            page=1,
            per_page=20,
        )

        assert result_paused["pagination"]["total"] == 1

    async def test_update_prescription(self, db_session: AsyncSession) -> None:
        """Test updating a prescription."""
        # Setup
        tenant = Tenant(id=uuid4(), name="Test Tenant")
        db_session.add(tenant)
        await db_session.commit()

        patient = Patient(
            id=uuid4(),
            tenant_id=tenant.id,
            c_first_name="Test",
            c_last_name="Patient",
        )
        db_session.add(patient)
        await db_session.commit()

        service = PrescriptionService(tenant_id=tenant.id)

        # Create
        create_req = PrescriptionRequest(
            patient_id=patient.id,
            title="Original",
            status="active",
            items=[
                PrescriptionItemRequest(
                    medication_label="Med 1",
                    medication_cis=None,
                    dose=None,
                    frequency=FrequencySchema(pattern="1x/jour"),
                ),
            ],
        )
        prescription = await service.create(create_req)

        # Update
        update_req = PrescriptionRequest(
            patient_id=patient.id,
            title="Updated",
            status="paused",
            items=[
                PrescriptionItemRequest(
                    medication_label="Med 2",
                    medication_cis=None,
                    dose=DoseSchema(value=200, unit="mg"),
                    frequency=FrequencySchema(pattern="2x/jour", times_per_day=2),
                ),
                PrescriptionItemRequest(
                    medication_label="Med 3",
                    medication_cis=None,
                    dose=None,
                    frequency=FrequencySchema(pattern="1x/jour"),
                ),
            ],
        )
        updated = await service.update(prescription.id, update_req)

        assert updated.title == "Updated"
        assert updated.status == "paused"
        assert len(updated.items) == 2
        assert updated.items[0].medication_label in ["Med 2", "Med 3"]

    async def test_update_status_only(self, db_session: AsyncSession) -> None:
        """Test updating only the status."""
        # Setup
        tenant = Tenant(id=uuid4(), name="Test Tenant")
        db_session.add(tenant)
        await db_session.commit()

        patient = Patient(
            id=uuid4(),
            tenant_id=tenant.id,
            c_first_name="Test",
            c_last_name="Patient",
        )
        db_session.add(patient)
        await db_session.commit()

        service = PrescriptionService(tenant_id=tenant.id)

        # Create
        create_req = PrescriptionRequest(
            patient_id=patient.id,
            title="Test",
            status="active",
            items=[
                PrescriptionItemRequest(
                    medication_label="Med",
                    medication_cis=None,
                    dose=None,
                    frequency=FrequencySchema(pattern="1x/jour"),
                ),
            ],
        )
        prescription = await service.create(create_req)

        # Update status
        status_req = StatusUpdateRequest(status="stopped")
        updated = await service.update_status(prescription.id, status_req)

        assert updated.status == "stopped"
        assert updated.title == "Test"  # Other fields unchanged

    async def test_delete_prescription(self, db_session: AsyncSession) -> None:
        """Test deleting a prescription."""
        # Setup
        tenant = Tenant(id=uuid4(), name="Test Tenant")
        db_session.add(tenant)
        await db_session.commit()

        patient = Patient(
            id=uuid4(),
            tenant_id=tenant.id,
            c_first_name="Test",
            c_last_name="Patient",
        )
        db_session.add(patient)
        await db_session.commit()

        service = PrescriptionService(tenant_id=tenant.id)

        # Create
        request = PrescriptionRequest(
            patient_id=patient.id,
            items=[
                PrescriptionItemRequest(
                    medication_label="Med",
                    medication_cis=None,
                    dose=None,
                    frequency=FrequencySchema(pattern="1x/jour"),
                ),
            ],
        )
        prescription = await service.create(request)
        prescription_id = prescription.id

        # Delete
        result = await service.delete(prescription_id)
        assert result is True

        # Verify deleted
        with pytest.raises(HTTPException) as exc_info:
            await service.get(prescription_id)

        assert exc_info.value.status_code == 404

    async def test_tenant_isolation(self, db_session: AsyncSession) -> None:
        """Test that tenant isolation works correctly."""
        # Setup two tenants
        tenant1 = Tenant(id=uuid4(), name="Tenant 1")
        tenant2 = Tenant(id=uuid4(), name="Tenant 2")
        db_session.add_all([tenant1, tenant2])
        await db_session.commit()

        patient1 = Patient(
            id=uuid4(),
            tenant_id=tenant1.id,
            c_first_name="Patient",
            c_last_name="One",
        )
        patient2 = Patient(
            id=uuid4(),
            tenant_id=tenant2.id,
            c_first_name="Patient",
            c_last_name="Two",
        )
        db_session.add_all([patient1, patient2])
        await db_session.commit()

        # Create services
        service1 = PrescriptionService(tenant_id=tenant1.id)
        service2 = PrescriptionService(tenant_id=tenant2.id)

        # Create prescription in tenant1
        request = PrescriptionRequest(
            patient_id=patient1.id,
            items=[
                PrescriptionItemRequest(
                    medication_label="Med",
                    medication_cis=None,
                    dose=None,
                    frequency=FrequencySchema(pattern="1x/jour"),
                ),
            ],
        )
        prescription1 = await service1.create(request)

        # Try to access from tenant2
        with pytest.raises(HTTPException) as exc_info:
            await service2.get(prescription1.id)

        assert exc_info.value.status_code == 404


class TestPrescriptionItemManagement:
    """Tests for individual item management operations."""

    async def test_add_item_to_prescription(self, db_session: AsyncSession) -> None:
        """Test adding a new item to an existing prescription."""
        # Setup
        tenant = Tenant(id=uuid4(), name="Test Tenant")
        db_session.add(tenant)
        await db_session.commit()

        patient = Patient(
            id=uuid4(),
            tenant_id=tenant.id,
            c_first_name="Test",
            c_last_name="Patient",
        )
        db_session.add(patient)
        await db_session.commit()

        service = PrescriptionService(tenant_id=tenant.id)

        # Create prescription with 1 item
        request = PrescriptionRequest(
            patient_id=patient.id,
            items=[
                PrescriptionItemRequest(
                    medication_label="Med 1",
                    medication_cis=None,
                    dose=None,
                    frequency=FrequencySchema(pattern="1x/jour"),
                ),
            ],
        )
        prescription = await service.create(request)
        assert len(prescription.items) == 1

        # Add item
        new_item = PrescriptionItemRequest(
            medication_label="Med 2",
            medication_cis=12345678,
            dose=DoseSchema(value=500, unit="mg"),
            frequency=FrequencySchema(
                pattern="2x/jour",
                times_per_day=2,
                moments=["matin", "soir"],
            ),
        )
        updated = await service.add_item(prescription.id, new_item)

        assert len(updated.items) == 2
        new_item_resp = next(i for i in updated.items if i.medication_label == "Med 2")
        assert new_item_resp.medication_cis == 12345678
        assert new_item_resp.dose.value == 500

    async def test_update_item(self, db_session: AsyncSession) -> None:
        """Test updating an existing item."""
        # Setup
        tenant = Tenant(id=uuid4(), name="Test Tenant")
        db_session.add(tenant)
        await db_session.commit()

        patient = Patient(
            id=uuid4(),
            tenant_id=tenant.id,
            c_first_name="Test",
            c_last_name="Patient",
        )
        db_session.add(patient)
        await db_session.commit()

        service = PrescriptionService(tenant_id=tenant.id)

        # Create
        request = PrescriptionRequest(
            patient_id=patient.id,
            items=[
                PrescriptionItemRequest(
                    medication_label="Original Med",
                    medication_cis=111,
                    dose=DoseSchema(value=100, unit="mg"),
                    frequency=FrequencySchema(pattern="1x/jour"),
                ),
            ],
        )
        prescription = await service.create(request)
        item_id = prescription.items[0].id

        # Update item
        update_item_req = PrescriptionItemRequest(
            medication_label="Updated Med",
            medication_cis=222,
            dose=DoseSchema(value=200, unit="mg"),
            frequency=FrequencySchema(pattern="3x/jour", times_per_day=3),
        )
        updated = await service.update_item(prescription.id, item_id, update_item_req)

        assert len(updated.items) == 1
        updated_item = updated.items[0]
        assert updated_item.medication_label == "Updated Med"
        assert updated_item.medication_cis == 222
        assert updated_item.dose.value == 200
        assert updated_item.frequency.times_per_day == 3

    async def test_get_item(self, db_session: AsyncSession) -> None:
        """Test getting a specific item."""
        # Setup
        tenant = Tenant(id=uuid4(), name="Test Tenant")
        db_session.add(tenant)
        await db_session.commit()

        patient = Patient(
            id=uuid4(),
            tenant_id=tenant.id,
            c_first_name="Test",
            c_last_name="Patient",
        )
        db_session.add(patient)
        await db_session.commit()

        service = PrescriptionService(tenant_id=tenant.id)

        # Create with 2 items
        request = PrescriptionRequest(
            patient_id=patient.id,
            items=[
                PrescriptionItemRequest(
                    medication_label="Med 1",
                    medication_cis=None,
                    dose=None,
                    frequency=FrequencySchema(pattern="1x/jour"),
                ),
                PrescriptionItemRequest(
                    medication_label="Med 2",
                    medication_cis=None,
                    dose=None,
                    frequency=FrequencySchema(pattern="2x/jour"),
                ),
            ],
        )
        prescription = await service.create(request)
        item_id = prescription.items[1].id

        # Get specific item
        item = await service.get_item(prescription.id, item_id)

        assert item.id == item_id
        assert item.medication_label == "Med 2"

    async def test_delete_item(self, db_session: AsyncSession) -> None:
        """Test deleting an item."""
        # Setup
        tenant = Tenant(id=uuid4(), name="Test Tenant")
        db_session.add(tenant)
        await db_session.commit()

        patient = Patient(
            id=uuid4(),
            tenant_id=tenant.id,
            c_first_name="Test",
            c_last_name="Patient",
        )
        db_session.add(patient)
        await db_session.commit()

        service = PrescriptionService(tenant_id=tenant.id)

        # Create with 2 items
        request = PrescriptionRequest(
            patient_id=patient.id,
            items=[
                PrescriptionItemRequest(
                    medication_label="Med 1",
                    medication_cis=None,
                    dose=None,
                    frequency=FrequencySchema(pattern="1x/jour"),
                ),
                PrescriptionItemRequest(
                    medication_label="Med 2",
                    medication_cis=None,
                    dose=None,
                    frequency=FrequencySchema(pattern="2x/jour"),
                ),
            ],
        )
        prescription = await service.create(request)
        item_id = prescription.items[0].id

        # Delete item
        updated = await service.delete_item(prescription.id, item_id)

        assert len(updated.items) == 1
        assert updated.items[0].medication_label == "Med 2"

    async def test_delete_last_item_fails(self, db_session: AsyncSession) -> None:
        """Test that deleting the last item fails."""
        # Setup
        tenant = Tenant(id=uuid4(), name="Test Tenant")
        db_session.add(tenant)
        await db_session.commit()

        patient = Patient(
            id=uuid4(),
            tenant_id=tenant.id,
            c_first_name="Test",
            c_last_name="Patient",
        )
        db_session.add(patient)
        await db_session.commit()

        service = PrescriptionService(tenant_id=tenant.id)

        # Create with 1 item
        request = PrescriptionRequest(
            patient_id=patient.id,
            items=[
                PrescriptionItemRequest(
                    medication_label="Med",
                    medication_cis=None,
                    dose=None,
                    frequency=FrequencySchema(pattern="1x/jour"),
                ),
            ],
        )
        prescription = await service.create(request)
        item_id = prescription.items[0].id

        # Try to delete last item
        with pytest.raises(HTTPException) as exc_info:
            await service.delete_item(prescription.id, item_id)

        assert exc_info.value.status_code == 400
        assert "at least 1 item" in str(exc_info.value.detail).lower()

    async def test_item_not_found(self, db_session: AsyncSession) -> None:
        """Test 404 when item doesn't exist."""
        # Setup
        tenant = Tenant(id=uuid4(), name="Test Tenant")
        db_session.add(tenant)
        await db_session.commit()

        patient = Patient(
            id=uuid4(),
            tenant_id=tenant.id,
            c_first_name="Test",
            c_last_name="Patient",
        )
        db_session.add(patient)
        await db_session.commit()

        service = PrescriptionService(tenant_id=tenant.id)

        # Create
        request = PrescriptionRequest(
            patient_id=patient.id,
            items=[
                PrescriptionItemRequest(
                    medication_label="Med",
                    medication_cis=None,
                    dose=None,
                    frequency=FrequencySchema(pattern="1x/jour"),
                ),
            ],
        )
        prescription = await service.create(request)

        # Try to get non-existent item
        with pytest.raises(HTTPException) as exc_info:
            await service.get_item(prescription.id, uuid4())

        assert exc_info.value.status_code == 404


class TestPrescriptionDocumentHandling:
    """Tests for document upload/download operations."""

    async def test_upload_document_mocked(self, db_session: AsyncSession) -> None:
        """Test document upload with mocked S3 client."""
        # Setup
        tenant = Tenant(id=uuid4(), name="Test Tenant")
        db_session.add(tenant)
        await db_session.commit()

        patient = Patient(
            id=uuid4(),
            tenant_id=tenant.id,
            c_first_name="Test",
            c_last_name="Patient",
        )
        db_session.add(patient)
        await db_session.commit()

        # Mock S3 client
        mock_s3 = AsyncMock()
        mock_s3.upload_file.return_value = "test-s3-key"

        service = PrescriptionService(tenant_id=tenant.id, s3_client=mock_s3)

        # Create prescription
        request = PrescriptionRequest(
            patient_id=patient.id,
            items=[
                PrescriptionItemRequest(
                    medication_label="Med",
                    medication_cis=None,
                    dose=None,
                    frequency=FrequencySchema(pattern="1x/jour"),
                ),
            ],
        )
        prescription = await service.create(request)

        # Mock file upload
        mock_file = AsyncMock()
        mock_file.filename = "ordonnance.pdf"
        mock_file.content_type = "application/pdf"
        mock_file.size = 1024
        mock_file.read = AsyncMock(return_value=b"fake pdf content")

        # Upload document
        updated = await service.upload_document(prescription.id, mock_file)

        assert updated.has_document is True
        assert updated.document_file_name == "ordonnance.pdf"
        assert updated.document_file_size == 1024
        assert updated.document_mime_type == "application/pdf"
        assert updated.document_uploaded_at is not None

        mock_s3.upload_file.assert_called_once()

    async def test_get_document_url_mocked(self, db_session: AsyncSession) -> None:
        """Test getting document URL with mocked S3."""
        # Setup
        tenant = Tenant(id=uuid4(), name="Test Tenant")
        db_session.add(tenant)
        await db_session.commit()

        patient = Patient(
            id=uuid4(),
            tenant_id=tenant.id,
            c_first_name="Test",
            c_last_name="Patient",
        )
        db_session.add(patient)
        await db_session.commit()

        # Mock S3
        mock_s3 = AsyncMock()
        mock_s3.upload_file.return_value = "test-s3-key"
        mock_s3.generate_presigned_url.return_value = (
            "https://s3.example.com/presigned-url"
        )

        service = PrescriptionService(tenant_id=tenant.id, s3_client=mock_s3)

        # Create prescription
        request = PrescriptionRequest(
            patient_id=patient.id,
            items=[
                PrescriptionItemRequest(
                    medication_label="Med",
                    medication_cis=None,
                    dose=None,
                    frequency=FrequencySchema(pattern="1x/jour"),
                ),
            ],
        )
        prescription = await service.create(request)

        # Upload mock file
        mock_file = AsyncMock()
        mock_file.filename = "test.pdf"
        mock_file.content_type = "application/pdf"
        mock_file.size = 1024
        mock_file.read = AsyncMock(return_value=b"content")

        await service.upload_document(prescription.id, mock_file)

        # Get URL
        url = await service.get_document_url(prescription.id)

        assert url == "https://s3.example.com/presigned-url"
        mock_s3.generate_presigned_url.assert_called_once()

    async def test_delete_document_mocked(self, db_session: AsyncSession) -> None:
        """Test deleting document with mocked S3."""
        # Setup
        tenant = Tenant(id=uuid4(), name="Test Tenant")
        db_session.add(tenant)
        await db_session.commit()

        patient = Patient(
            id=uuid4(),
            tenant_id=tenant.id,
            c_first_name="Test",
            c_last_name="Patient",
        )
        db_session.add(patient)
        await db_session.commit()

        # Mock S3
        mock_s3 = AsyncMock()
        mock_s3.upload_file.return_value = "test-s3-key"
        mock_s3.delete_file.return_value = True

        service = PrescriptionService(tenant_id=tenant.id, s3_client=mock_s3)

        # Create and upload
        request = PrescriptionRequest(
            patient_id=patient.id,
            items=[
                PrescriptionItemRequest(
                    medication_label="Med",
                    medication_cis=None,
                    dose=None,
                    frequency=FrequencySchema(pattern="1x/jour"),
                ),
            ],
        )
        prescription = await service.create(request)

        mock_file = AsyncMock()
        mock_file.filename = "test.pdf"
        mock_file.content_type = "application/pdf"
        mock_file.size = 1024
        mock_file.read = AsyncMock(return_value=b"content")

        await service.upload_document(prescription.id, mock_file)

        # Delete document
        result = await service.delete_document(prescription.id)

        assert result is True
        mock_s3.delete_file.assert_called_once()

        # Verify metadata cleared
        updated = await service.get(prescription.id)
        assert updated.has_document is False
        assert updated.document_file_name is None
