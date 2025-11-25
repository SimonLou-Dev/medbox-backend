import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medbox.core.db.base import Base
from ._mixins import IDMixin, TimestampMixin
from ..types import EncryptedString


class User(Base, IDMixin, TimestampMixin):
    """
    Utilisateur logique Medbox (lié à Keycloak via subject_id).
    Pas de mot de passe ici, tout est externalisé.
    """

    __tablename__ = 'users'

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
    )

    keycloak_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    c_full_name: Mapped[str | None] = mapped_column(EncryptedString(), nullable=True)

    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="patient|caregiver|tenant_admin|global_admin (côté métier)",
    )
    tenant: Mapped["Tenant"] = relationship(back_populates="users")
    created_prescriptions: Mapped[list["Prescription"]] = relationship(
        back_populates="created_by"
    )


