from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medbox.core.db.base import Base
from ._mixins import IDMixin, TimestampMixin


class Patient(Base, IDMixin, TimestampMixin):
    __tablename__ = "patients"



    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Identifiant externe (DPI, etc.)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Données sensibles chiffrées
    c_first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    c_last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    c_address: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    c_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    birth_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


    tenant: Mapped["Tenant"] = relationship(back_populates="patients")
    boxes: Mapped[list["Box"]] = relationship(back_populates="patient")
    wheels: Mapped[list["Wheel"]] = relationship(back_populates="patient")
    prescriptions: Mapped[list["Prescription"]] = relationship(back_populates="patient")
    events: Mapped[list["Event"]] = relationship(back_populates="patient")
