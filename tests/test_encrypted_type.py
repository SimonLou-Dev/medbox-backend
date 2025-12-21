# tests/test_encrypted_type.py

import uuid

import pytest
from sqlalchemy import text

from medbox.core.db.models import Tenant
from medbox.core.db.models.patient import Patient


@pytest.mark.asyncio
async def test_encrypted_string_in_model(db_session):
    tenant = Tenant(
        name=f"test tenant {uuid.uuid4()}",
    )

    db_session.add(tenant)
    await db_session.commit()

    patient = Patient(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        c_first_name="Jean",
        c_last_name="Dupont",
        c_address="1 rue du test",
        c_phone="0600000000",
    )

    db_session.add(patient)
    await db_session.commit()

    result = await db_session.get(Patient, patient.id)
    assert result.c_first_name == "Jean"

    # Test raw SQL query for encryption verification
    row = await db_session.execute(
        text("SELECT c_first_name FROM patients WHERE id = :id"),
        {"id": str(patient.id)},
    )
    encrypted_value = row.scalar_one_or_none()

    # Data should be encrypted at database level
    if encrypted_value:
        assert encrypted_value != "Jean"
        assert isinstance(encrypted_value, str)
