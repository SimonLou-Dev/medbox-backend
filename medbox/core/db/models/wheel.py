from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medbox.core.db.base import Base
from ._mixins import IDMixin, TimestampMixin


class Wheel(Base, IDMixin, TimestampMixin):
    """
    Roue contenant les médicaments.
    Préparée en amont, associée dynamiquement à une box et un patient.
    """

    __tablename__ = "wheels"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )

    wheel_uid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)

    # Roue éventuellement liée à un patient et/ou une box
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("patients.id", ondelete="SET NULL"),
        nullable=True,
    )
    box_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("boxes.id", ondelete="SET NULL"),
        nullable=True,
    )

    slot_count: Mapped[int] = mapped_column(Integer, nullable=False, default=28)

    status: Mapped[str] = mapped_column(
        String(50),
        default="prepared",  # prepared|mounted|in_stock|empty|error
        nullable=False,
    )



    tenant: Mapped["Tenant"] = relationship(back_populates="wheels")
    patient: Mapped["Patient | None"] = relationship(back_populates="wheels")
    box: Mapped["Box | None"] = relationship(back_populates="wheels")
    slots: Mapped[list["WheelSlot"]] = relationship(back_populates="wheel")
    events: Mapped[list["Event"]] = relationship(back_populates="wheel")
