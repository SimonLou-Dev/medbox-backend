from datetime import datetime
import uuid

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medbox.core.db.base import Base
from ._mixins import IDMixin, TimestampMixin


class Tenant(Base, IDMixin, TimestampMixin):
    __tablename__ = 'tenants'

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    users: Mapped[list["User"]] = relationship(back_populates="tenant")
    patients: Mapped[list["Patient"]] = relationship(back_populates="tenant")
    boxes: Mapped[list["Box"]] = relationship(back_populates="tenant")
    wheels: Mapped[list["Wheel"]] = relationship(back_populates="tenant")
    prescriptions: Mapped[list["Prescription"]] = relationship(back_populates="tenant")
    events: Mapped[list["Event"]] = relationship(back_populates="tenant")
    telemetry: Mapped[list["Telemetry"]] = relationship(back_populates="tenant")

