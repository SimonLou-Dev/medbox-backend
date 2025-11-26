"""Définition du modèle case de roue."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TCH003

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medbox.core.db.base import Base
from medbox.core.db.models._mixins import IDMixin, TimestampMixin
from medbox.core.db.types import EncryptedString

if TYPE_CHECKING:
    from medbox.core.db.models.wheel import Wheel
    from medbox.core.db.models.wheel_slot_prescription_item import (
        WheelSlotPrescriptionItem,
    )


class WheelSlot(Base, IDMixin, TimestampMixin):
    """Un compartiment physique sur une roue."""

    __tablename__ = "wheel_slots"

    wheel_id: Mapped[UUID] = mapped_column(
        ForeignKey("wheels.id", ondelete="CASCADE"),
        nullable=False,
    )

    index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Index du compartiment sur la roue (0..slot_count-1)",
    )

    c_label: Mapped[str | None] = mapped_column(
        EncryptedString(),
        nullable=True,
        doc="Label chiffré éventuel (ex: matin, midi...)",
    )

    wheel: Mapped[Wheel] = relationship(back_populates="slots")
    prescription_links: Mapped[list[WheelSlotPrescriptionItem]] = relationship(
        back_populates="wheel_slot",
    )
