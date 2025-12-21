"""Définitions du modèles Événements."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medbox.core.db.base import Base
from medbox.core.db.models._mixins import IDMixin, TimestampMixin

if TYPE_CHECKING:
    from medbox.core.db.models.box import Box
    from medbox.core.db.models.patient import Patient
    from medbox.core.db.models.tenant import Tenant
    from medbox.core.db.models.wheel import Wheel


class Event(Base, IDMixin, TimestampMixin):
    """Événements liés aux boxes / wheels / patients."""

    __tablename__ = "events"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )

    box_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("boxes.id", ondelete="SET NULL"),
        nullable=True,
    )
    wheel_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("wheels.id", ondelete="SET NULL"),
        nullable=True,
    )
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("patients.id", ondelete="SET NULL"),
        nullable=True,
    )

    type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="Ex: DISTRIBUTION_OK, DISTRIBUTION_MISSED, BOX_OPEN, SHOCK, ERROR_MOTOR...",
    )

    payload: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        doc="Détails spécifiques (slot index, code erreur, etc.)",
    )

    tenant: Mapped[Tenant] = relationship(back_populates="events")
    box: Mapped[Box | None] = relationship(back_populates="events")
    wheel: Mapped[Wheel | None] = relationship(back_populates="events")
    patient: Mapped[Patient | None] = relationship(back_populates="events")
