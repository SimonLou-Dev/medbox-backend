from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medbox.core.db.base import Base
from ._mixins import IDMixin, TimestampMixin


class Telemetry(Base, IDMixin, TimestampMixin):
    """
    Télémétrie technique de la box : batterie, RSSI, température, erreurs, etc.
    L'agrégation pour Grafana se fera ailleurs.
    """

    __tablename__ = "telemetry"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )

    box_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("boxes.id", ondelete="SET NULL"),
        nullable=True,
    )

    metric: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="Ex: battery_level, rssi, motor_current, temperature",
    )

    value_number: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


    tenant: Mapped["Tenant"] = relationship(back_populates="telemetry")
    box: Mapped["Box | None"] = relationship(back_populates="telemetry")
