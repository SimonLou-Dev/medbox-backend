from __future__ import annotations

import uuid

from sqlalchemy import String, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medbox.core.db.base import Base
from ._mixins import IDMixin, TimestampMixin


class WheelSlot(Base, IDMixin, TimestampMixin):
    """
    Un compartiment physique sur une roue.
    """

    __tablename__ = "wheel_slots"

    wheel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wheels.id", ondelete="CASCADE"),
        nullable=False,
    )

    index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Index du compartiment sur la roue (0..slot_count-1)",
    )

    c_label: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Label chiffré éventuel (ex: matin, midi...)",
    )

    wheel: Mapped["Wheel"] = relationship(back_populates="slots")
    prescription_links: Mapped[list["WheelSlotPrescriptionItem"]] = relationship(
        back_populates="wheel_slot"
    )
