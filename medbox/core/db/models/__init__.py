from __future__ import annotations

from medbox.core.db.base import Base

# Importer tous les modèles ici pour qu'Alembic les voie
from .tenant import Tenant
from .user import User
from .patient import Patient
from .box import Box
from .wheel import Wheel
from .wheel_slot import WheelSlot
from .wheel_slot_prescription_item import WheelSlotPrescriptionItem
from .global_medication import GlobalMedication
from .prescription import Prescription
from .prescription_item import PrescriptionItem
from .event import Event
from .telemetry import Telemetry

__all__ = [
    "Base",
    "Tenant",
    "User",
    "Patient",
    "Box",
    "Wheel",
    "WheelSlot",
    "WheelSlotPrescriptionItem",
    "GlobalMedication",
    "Prescription",
    "PrescriptionItem",
    "Event",
    "Telemetry",
]
