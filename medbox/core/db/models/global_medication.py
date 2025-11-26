"""Référentiel global de médicaments."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from medbox.core.db.base import Base
from medbox.core.db.models._mixins import IDMixin, TimestampMixin


class GlobalMedication(Base, IDMixin, TimestampMixin):
    """Référentiel global de médicaments."""

    __tablename__ = "global_medications"

    code: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        doc="Code interne / CIP / etc.",
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    form: Mapped[str | None] = mapped_column(String(128), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
