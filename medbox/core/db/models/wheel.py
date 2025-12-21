"""Définition du modèle roue."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medbox.core.db.base import Base
from medbox.core.db.models._mixins import IDMixin, TimestampMixin

if TYPE_CHECKING:
    from medbox.core.db.models.box import Box
    from medbox.core.db.models.event import Event
    from medbox.core.db.models.patient import Patient
    from medbox.core.db.models.tenant import Tenant
    from medbox.core.db.models.wheel_slot import WheelSlot


class Wheel(Base, IDMixin, TimestampMixin):
    """Roue contenant les médicaments."""

    __tablename__ = "wheels"

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )

    wheel_uid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)

    # Roue éventuellement liée à un patient et/ou une box
    patient_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("patients.id", ondelete="SET NULL"),
        nullable=True,
    )
    box_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("boxes.id", ondelete="SET NULL"),
        nullable=True,
    )

    slot_count: Mapped[int] = mapped_column(Integer, nullable=False, default=28)

    status: Mapped[str] = mapped_column(
        String(50),
        default="prepared",  # prepared|mounted|in_stock|empty|error
        nullable=False,
    )

    tenant: Mapped[Tenant] = relationship(back_populates="wheels")
    patient: Mapped[Patient | None] = relationship(back_populates="wheels")
    box: Mapped[Box | None] = relationship(back_populates="wheels")
    slots: Mapped[list[WheelSlot]] = relationship(back_populates="wheel")
    events: Mapped[list[Event]] = relationship(back_populates="wheel")
