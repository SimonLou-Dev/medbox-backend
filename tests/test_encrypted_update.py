# tests/test_encrypted_update.py

import uuid

import pytest

from medbox.core.db.models import Tenant
from medbox.core.db.models.patient import Patient


@pytest.mark.asyncio
async def test_encrypted_update(test_session):
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

    patient.c_first_name = "Bob"
    await test_session.commit()

    result = await test_session.get(Patient, patient.id)
    assert result.c_first_name == "Bob"
