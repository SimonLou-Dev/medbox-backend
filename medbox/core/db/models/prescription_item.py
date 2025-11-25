from __future__ import annotations

import uuid

from sqlalchemy import String, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medbox.core.db.base import Base
from ._mixins import IDMixin, TimestampMixin


class PrescriptionItem(Base, IDMixin, TimestampMixin):
    """
    Un médicament dans une ordonnance, avec sa posologie.
    Exemple : Metformine 500mg, 1 cp matin et soir.
    """

    __tablename__ = "prescription_items"

    prescription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("prescriptions.id", ondelete="CASCADE"),
        nullable=False,
    )

    medication_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("global_medications.id", ondelete="SET NULL"),
        nullable=True,
    )

    medication_label: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Libellé tel que saisi sur l'ordonnance (pour trace).",
    )

    dose: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        doc="Ex: '500 mg', '1 cp', '20 gouttes'",
    )

    frequency: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        doc="Description humaine de la fréquence ex: '3x/jour', 'matin+soir'",
    )

    # Tu pourras raffiner plus tard (matin/midi/soir, jours de la semaine etc.)
    extra_instructions: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    prescription: Mapped["Prescription"] = relationship(back_populates="items")
    medication: Mapped["GlobalMedication | None"] = relationship()
    wheel_slot_links: Mapped[list["WheelSlotPrescriptionItem"]] = relationship(
        back_populates="prescription_item"
    )
