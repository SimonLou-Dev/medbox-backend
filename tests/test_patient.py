"""Integration tests for PatientService with real database."""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from medbox.core.db.models.tenant import Tenant
from medbox.core.dto.patient import PatientRequest
from medbox.core.exceptions.not_found import ModelNotFoundError
from medbox.core.services.patient import PatientService

pytestmark = pytest.mark.asyncio


class TestPatientServiceIntegration:
    """Integration tests for PatientService with database."""

    async def test_create_and_get_patient(self, db_session: AsyncSession) -> None:
        """Test creating and retrieving a patient."""
        # Setup
        tenant = Tenant(id=uuid4(), name="Test Tenant")
        db_session.add(tenant)
        await db_session.commit()

        # Create service
        service = PatientService(tenant_id=tenant.id)

        # Create patient
        request = PatientRequest(
            c_first_name="John",
            c_last_name="Doe",
            external_id="EHR-12345",
        )
        created = await service.create(request)

        assert created.c_first_name == "John"
        assert created.c_last_name == "Doe"
        assert created.external_id == "EHR-12345"

        # Get patient
        retrieved = await service.get(created.id)

        assert retrieved.id == created.id
        assert retrieved.c_first_name == "John"

    async def test_list_patients(self, db_session: AsyncSession) -> None:
        """Test listing patients."""
        # Setup
        tenant = Tenant(id=uuid4(), name="Test Tenant")
        db_session.add(tenant)
        await db_session.commit()

        # Create service and add patients
        service = PatientService(tenant_id=tenant.id)

        patients_created = []
        for i in range(3):
            request = PatientRequest(
                c_first_name=f"Patient{i}",
                c_last_name="Test",
            )
            p = await service.create(request)
            patients_created.append(p)

        # List patients
        result = await service.list()

        assert len(result) == 3
        ids = {p.id for p in result}
        created_ids = {p.id for p in patients_created}
        assert ids == created_ids

    async def test_update_patient(self, db_session: AsyncSession) -> None:
        """Test updating a patient."""
        # Setup
        tenant = Tenant(id=uuid4(), name="Test Tenant")
        db_session.add(tenant)
        await db_session.commit()

        service = PatientService(tenant_id=tenant.id)

        # Create patient
        create_req = PatientRequest(
            c_first_name="John",
            c_last_name="Doe",
        )
        patient = await service.create(create_req)

        # Update patient
        update_req = PatientRequest(
            c_first_name="Jane",
            c_last_name="Smith",
        )
        updated = await service.update(patient.id, update_req)

        assert updated.c_first_name == "Jane"
        assert updated.c_last_name == "Smith"

    async def test_delete_patient(self, db_session: AsyncSession) -> None:
        """Test deleting a patient."""
        # Setup
        tenant = Tenant(id=uuid4(), name="Test Tenant")
        db_session.add(tenant)
        await db_session.commit()

        service = PatientService(tenant_id=tenant.id)

        # Create patient
        request = PatientRequest(
            c_first_name="John",
            c_last_name="Doe",
        )
        patient = await service.create(request)
        patient_id = patient.id

        # Delete patient
        await service.delete(patient_id)

        # Verify deleted
        with pytest.raises(ModelNotFoundError):
            await service.get(patient_id)

    async def test_list_paginated(self, db_session: AsyncSession) -> None:
        """Test paginated list."""
        # Setup
        tenant = Tenant(id=uuid4(), name="Test Tenant")
        db_session.add(tenant)
        await db_session.commit()

        service = PatientService(tenant_id=tenant.id)

        # Create 25 patients
        for i in range(25):
            request = PatientRequest(
                c_first_name=f"Patient{i:02d}",
                c_last_name="Test",
            )
            await service.create(request)

        # Get first page
        result = await service.list_paginated(page=1, per_page=10)

        assert result.total == 25
        assert len(result.data) == 10

    async def test_list_paginated_with_search(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test paginated list with search."""
        # Setup
        tenant = Tenant(id=uuid4(), name="Test Tenant")
        db_session.add(tenant)
        await db_session.commit()

        service = PatientService(tenant_id=tenant.id)

        # Create patients
        await service.create(PatientRequest(c_first_name="John", c_last_name="Smith"))
        await service.create(PatientRequest(c_first_name="Jane", c_last_name="Smith"))
        await service.create(PatientRequest(c_first_name="Bob", c_last_name="Johnson"))

        # Search for Smith
        result = await service.list_paginated(page=1, per_page=10, search="Smith")

        assert result.total == 2
        assert len(result.data) == 2

    async def test_tenant_isolation(self, db_session: AsyncSession) -> None:
        """Test that services respect tenant isolation."""
        # Setup: Create 2 tenants
        tenant_a = Tenant(id=uuid4(), name="Tenant A")
        tenant_b = Tenant(id=uuid4(), name="Tenant B")
        db_session.add_all([tenant_a, tenant_b])
        await db_session.commit()

        # Create services for each tenant
        service_a = PatientService(tenant_id=tenant_a.id)
        service_b = PatientService(tenant_id=tenant_b.id)

        # Add patients to tenant A
        await service_a.create(PatientRequest(c_first_name="Alice", c_last_name="A"))
        await service_a.create(PatientRequest(c_first_name="Andrew", c_last_name="A"))

        # Add patient to tenant B
        await service_b.create(PatientRequest(c_first_name="Bob", c_last_name="B"))

        # Verify isolation
        result_a = await service_a.list()
        result_b = await service_b.list()

        assert len(result_a) == 2
        assert len(result_b) == 1
        assert all(p.c_last_name == "A" for p in result_a)
        assert result_b[0].c_last_name == "B"
