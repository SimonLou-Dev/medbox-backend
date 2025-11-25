from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medbox.core.db.base import Base
from ._mixins import IDMixin, TimestampMixin


class Box(Base, IDMixin, TimestampMixin):
    """
    Boîtier physique de distribution.
    La logique métier reste côté API, la box exécute les ordres.
    """

    __tablename__ = "boxes"


    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
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
    software_version: Mapped[str | None] = mapped_column(String(50))

    timezone: Mapped[str | None] = mapped_column(String(64))

    battery_level: Mapped[int | None] = mapped_column(
        Integer, doc="Pourcentage 0-100", nullable=True
    )
    on_battery: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))



    tenant: Mapped["Tenant"] = relationship(back_populates="boxes")
    patient: Mapped["Patient | None"] = relationship(back_populates="boxes")
    wheels: Mapped[list["Wheel"]] = relationship(back_populates="box")
    events: Mapped[list["Event"]] = relationship(back_populates="box")
    telemetry: Mapped[list["Telemetry"]] = relationship(back_populates="box")
