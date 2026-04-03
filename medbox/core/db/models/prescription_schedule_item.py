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
    from medbox.core.db.models.prescription import Prescription
    from medbox.core.db.models.prescription_item import PrescriptionItem
    from medbox.core.db.models.tenant import Tenant


class PrescriptionScheduleItem(Base, IDMixin, TimestampMixin):
    """Une prise planifiée calculée par le scheduler.

    Chaque instance représente un moment précis où une box doit
    distribuer un ou plusieurs médicaments pour un patient.

    Cycle de vie : pending → dispatched → taken | missed | error
    """

    __tablename__ = "prescription_schedule_items"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    prescription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("prescriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    prescription_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("prescription_items.id", ondelete="SET NULL"),
        nullable=True,
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
        doc="pending | dispatched | taken | missed | error",
    )

    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Horodatage de l'envoi de la commande à la box",
    )

    taken_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Horodatage de la prise confirmée par la box",
    )

    error_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Raison de l'erreur si status=error",
    )

    # Relations
    tenant: Mapped[Tenant] = relationship()
    prescription: Mapped[Prescription] = relationship()
    prescription_item: Mapped[PrescriptionItem | None] = relationship()
    box: Mapped[Box | None] = relationship()
