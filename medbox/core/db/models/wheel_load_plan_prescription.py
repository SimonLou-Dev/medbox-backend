"""Association entre un plan de chargement et les ordonnances incluses."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medbox.core.db.base import Base
from medbox.core.db.models._mixins import IDMixin, TimestampMixin

if TYPE_CHECKING:
    from medbox.core.db.models.prescription import Prescription
    from medbox.core.db.models.wheel_load_plan import WheelLoadPlan


class WheelLoadPlanPrescription(Base, IDMixin, TimestampMixin):
    """Lien entre un plan de chargement et une ordonnance.

    Un plan peut regrouper plusieurs ordonnances d'un même patient
    (ex: traitement principal + vitamines). La moulinette croise
    toutes les fréquences pour calculer la répartition dans les cases.
    """

    __tablename__ = "wheel_load_plan_prescriptions"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wheel_load_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    prescription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("prescriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relations
    plan: Mapped[WheelLoadPlan] = relationship(back_populates="prescriptions")
    prescription: Mapped[Prescription] = relationship()
