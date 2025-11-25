# tests/test_encrypted_type.py

import uuid

import pytest
from sqlalchemy import text

from medbox.core.db.models import Tenant
from medbox.core.db.models.patient import Patient


@pytest.mark.asyncio
async def test_encrypted_string_in_model(test_session):
    tenant = Tenant(
        name=f"test tenant {uuid.uuid4()}",
    )

    test_session.add(tenant)
    await test_session.commit()


    patient = Patient(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        c_first_name="Jean",
        c_last_name="Dupont",
        c_address="1 rue du test",
        c_phone="0600000000",
    )

    test_session.add(patient)
    await test_session.commit()

    result = await test_session.get(Patient, patient.id)
    assert result.c_first_name == "Jean"

    row = await test_session.execute(
        text("SELECT c_first_name FROM patients WHERE id = :id"),
        {"id": str(patient.id)},
    )
    encrypted_value = row.scalar_one()

    assert encrypted_value != "Jean"
    assert isinstance(encrypted_value, str)
