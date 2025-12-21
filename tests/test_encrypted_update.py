# tests/test_encrypted_update.py

import uuid

import pytest

from medbox.core.db.models import Tenant
from medbox.core.db.models.patient import Patient


@pytest.mark.asyncio
async def test_encrypted_update(db_session):
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

    patient.c_first_name = "Bob"
    await db_session.commit()

    result = await db_session.get(Patient, patient.id)
    assert result.c_first_name == "Bob"
