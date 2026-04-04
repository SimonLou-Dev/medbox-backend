"""Boîtier physique de distribution."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medbox.core.db.base import Base
from medbox.core.db.models._mixins import IDMixin, TimestampMixin

if TYPE_CHECKING:
    from medbox.core.db.models.event import Event
    from medbox.core.db.models.patient import Patient
    from medbox.core.db.models.telemetry import Telemetry
    from medbox.core.db.models.tenant import Tenant
    from medbox.core.db.models.wheel import Wheel


class Box(Base, IDMixin, TimestampMixin):
    """Boîtier physique de distribution."""

    __tablename__ = "boxes"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Identifiant physique (lecture sur la box, QR code, etc.)
    box_uid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)

    name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Association logique à un patient (peut changer dans le temps)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("patients.id", ondelete="SET NULL"),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="active",  # active|inactive|maintenance|error
        nullable=False,
    )

    firmware_version: Mapped[str | None] = mapped_column(String(50))
    timezone: Mapped[str | None] = mapped_column(String(64))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tenant: Mapped[Tenant] = relationship(back_populates="boxes")
    patient: Mapped[Patient | None] = relationship(back_populates="boxes")
    wheels: Mapped[list[Wheel]] = relationship(back_populates="box")
    events: Mapped[list[Event]] = relationship(back_populates="box")
    telemetry: Mapped[list[Telemetry]] = relationship(back_populates="box")
