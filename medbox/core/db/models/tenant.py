"""Table représentant un tenant."""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medbox.core.db.base import Base
from medbox.core.db.models._mixins import IDMixin, TimestampMixin

if TYPE_CHECKING:
    from medbox.core.db.models.box import Box
    from medbox.core.db.models.event import Event
    from medbox.core.db.models.invitation import Invitation
    from medbox.core.db.models.patient import Patient
    from medbox.core.db.models.prescription import Prescription
    from medbox.core.db.models.telemetry import Telemetry
    from medbox.core.db.models.user import User
    from medbox.core.db.models.wheel import Wheel


class Tenant(Base, IDMixin, TimestampMixin):
    """Table représentant un tenant."""

    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    users: Mapped[list["User"]] = relationship(back_populates="tenant")
    patients: Mapped[list["Patient"]] = relationship(back_populates="tenant")
    boxes: Mapped[list["Box"]] = relationship(back_populates="tenant")
    wheels: Mapped[list["Wheel"]] = relationship(back_populates="tenant")
    prescriptions: Mapped[list["Prescription"]] = relationship(back_populates="tenant")
    events: Mapped[list["Event"]] = relationship(back_populates="tenant")
    telemetry: Mapped[list["Telemetry"]] = relationship(back_populates="tenant")
    invitations: Mapped[list["Invitation"]] = relationship(
        back_populates="tenant",
        passive_deletes=True,
    )
