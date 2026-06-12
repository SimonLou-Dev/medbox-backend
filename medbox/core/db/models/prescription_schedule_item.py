"""Définition du modèle PrescriptionScheduleItem."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medbox.core.db.base import Base
from medbox.core.db.models._mixins import IDMixin, TimestampMixin

if TYPE_CHECKING:
    from medbox.core.db.models.box import Box
    from medbox.core.db.models.tenant import Tenant
    from medbox.core.db.models.wheel_load_plan import WheelLoadPlan
    from medbox.core.db.models.wheel_slot import WheelSlot


class PrescriptionScheduleItem(Base, IDMixin, TimestampMixin):
    """Une distribution planifiée correspondant à une case physique de la roue.

    Chaque instance représente un moment précis où la medbox fait tourner
    la roue pour libérer une case. Les médicaments dans cette case sont
    définis via wheel_slot → WheelSlotPrescriptionItem.

    Cycle de vie : pending → taken | error
    """

    __tablename__ = "prescription_schedule_items"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    wheel_load_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("wheel_load_plans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Plan de chargement qui a généré cet item",
    )

    wheel_slot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("wheel_slots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Case physique de la roue à distribuer",
    )

    box_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("boxes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        doc="Moment prévu pour la distribution",
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
        doc="pending | taken | error",
    )

    taken_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Horodatage de la distribution confirmée par la medbox",
    )

    error_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Raison de l'erreur si status=error",
    )

    # Relations
    tenant: Mapped[Tenant] = relationship()
    wheel_load_plan: Mapped[WheelLoadPlan | None] = relationship(
        back_populates="schedule_items",
    )
    wheel_slot: Mapped[WheelSlot | None] = relationship()
    box: Mapped[Box | None] = relationship()
