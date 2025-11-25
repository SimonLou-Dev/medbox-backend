from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medbox.core.db.base import Base
from ._mixins import IDMixin, TimestampMixin
from ..types import EncryptedString


class Prescription(Base, IDMixin, TimestampMixin):
    """
    Une ordonnance complète pour un patient.
    Exemple : ordonnance diabétologue, ordonnance généraliste, etc.
    """

    __tablename__ = "prescriptions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
    )

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    c_notes: Mapped[str | None] = mapped_column(EncryptedString(), nullable=True)

    status: Mapped[str] = mapped_column(
        String(50),
        default="active",  # active|paused|stopped|expired
        nullable=False,
    )

    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


    tenant: Mapped["Tenant"] = relationship(back_populates="prescriptions")
    patient: Mapped["Patient"] = relationship(back_populates="prescriptions")
    created_by: Mapped["User | None"] = relationship(
        back_populates="created_prescriptions"
    )
    items: Mapped[list["PrescriptionItem"]] = relationship(
        back_populates="prescription",
        cascade="all, delete-orphan",
    )
