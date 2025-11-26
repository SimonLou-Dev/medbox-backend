"""Modèle d'un utilsiateur."""

import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medbox.core.constants.enums import UserRoles, UserStatus
from medbox.core.db.base import Base
from medbox.core.db.models._mixins import IDMixin, TimestampMixin
from medbox.core.db.types import EncryptedString


class User(Base, IDMixin, TimestampMixin):
    """Utilisateur logique Medbox (lié à Keycloak via subject_id)."""

    __tablename__ = "users"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
    )

    keycloak_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    c_full_name: Mapped[str | None] = mapped_column(EncryptedString(), nullable=True)

    status: Mapped[UserStatus] = mapped_column(
        SAEnum(UserStatus),
        nullable=False,
        default=UserStatus.PENDING,
    )

    role: Mapped[UserRoles] = mapped_column(
        SAEnum(UserRoles),
        nullable=False,
        default=UserRoles.DEFAULT,
    )
    tenant: Mapped["Tenant"] = relationship(back_populates="users")
    created_prescriptions: Mapped[list["Prescription"]] = relationship(
        back_populates="created_by",
    )
