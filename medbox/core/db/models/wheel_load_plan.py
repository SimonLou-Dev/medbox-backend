"""Définition du modèle WheelLoadPlan."""

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
    from medbox.core.db.models.prescription_schedule_item import (
        PrescriptionScheduleItem,
    )
    from medbox.core.db.models.tenant import Tenant
    from medbox.core.db.models.user import User
    from medbox.core.db.models.wheel import Wheel
    from medbox.core.db.models.wheel_load_plan_prescription import (
        WheelLoadPlanPrescription,
    )


class WheelLoadPlan(Base, IDMixin, TimestampMixin):
    """Plan de chargement d'une roue pour une medbox.

    Représente l'étape intermédiaire entre la sélection d'ordonnances
    par le soignant et la création des distributions effectives.

    La moulinette calcule la répartition des médicaments dans les 21 cases
    utiles et produit la liste de remplissage que le soignant utilise pour
    charger la roue physiquement.

    Cycle de vie :
        draft      → plan calculé, liste de remplissage disponible
        confirmed  → soignant a confirmé le remplissage physique de la roue
        active     → roue chargée dans la medbox, schedule items créés
        exhausted  → toutes les cases ont été distribuées
        cancelled  → plan annulé avant ou après chargement
    """

    __tablename__ = "wheel_load_plans"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    wheel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wheels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    box_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("boxes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Medbox cible, définie au moment du chargement",
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="draft",
        index=True,
        doc="draft | confirmed | active | exhausted | cancelled",
    )

    valid_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Début de la période couverte par ce plan",
    )

    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Fin de la période couverte (dernière distribution prévue)",
    )

    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Moment où le soignant a confirmé le remplissage physique",
    )

    # Relations
    tenant: Mapped[Tenant] = relationship()
    created_by: Mapped[User | None] = relationship()
    wheel: Mapped[Wheel] = relationship()
    box: Mapped[Box | None] = relationship()
    prescriptions: Mapped[list[WheelLoadPlanPrescription]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
    )
    schedule_items: Mapped[list[PrescriptionScheduleItem]] = relationship(
        back_populates="wheel_load_plan",
    )
