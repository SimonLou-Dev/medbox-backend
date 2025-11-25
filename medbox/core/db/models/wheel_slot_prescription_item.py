from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medbox.core.db.base import Base
from ._mixins import IDMixin, TimestampMixin


class WheelSlotPrescriptionItem(Base, IDMixin, TimestampMixin):
    """
    Lien entre un compartiment de roue et un item d'ordonnance.
    Permet de dire : dans ce slot, il y a tel médicament de telle prescription.
    """

    __tablename__ = "wheel_slot_prescription_items"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    wheel_slot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wheel_slots.id", ondelete="CASCADE"),
        nullable=False,
    )

    prescription_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("prescription_items.id", ondelete="CASCADE"),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        doc="Nombre de pilules / unités dans le slot pour cet item",
    )

    wheel_slot: Mapped["WheelSlot"] = relationship(back_populates="prescription_links")
    prescription_item: Mapped["PrescriptionItem"] = relationship(
        back_populates="wheel_slot_links"
    )
