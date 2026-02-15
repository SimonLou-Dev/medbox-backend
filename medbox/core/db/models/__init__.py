"""Définitions des modèls."""

from __future__ import annotations

from medbox.core.db.base import Base
from medbox.core.db.models.box import Box
from medbox.core.db.models.event import Event
from medbox.core.db.models.global_medication import GlobalMedication
from medbox.core.db.models.invitation import Invitation
from medbox.core.db.models.patient import Patient
from medbox.core.db.models.prescription import Prescription
from medbox.core.db.models.prescription_item import PrescriptionItem
from medbox.core.db.models.telemetry import Telemetry

# Importer tous les modèles ici pour qu'Alembic les voie
from medbox.core.db.models.tenant import Tenant
from medbox.core.db.models.user import User
from medbox.core.db.models.wheel import Wheel
from medbox.core.db.models.wheel_slot import WheelSlot
from medbox.core.db.models.wheel_slot_prescription_item import WheelSlotPrescriptionItem

__all__ = [
    "Base",
    "Box",
    "Event",
    "GlobalMedication",
    "Invitation",
    "Patient",
    "Prescription",
    "PrescriptionItem",
    "Telemetry",
    "Tenant",
    "User",
    "Wheel",
    "WheelSlot",
    "WheelSlotPrescriptionItem",
]
