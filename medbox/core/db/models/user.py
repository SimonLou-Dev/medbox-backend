import uuid

from keycloak.authorization import Role
from sqlalchemy import ForeignKey, String, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medbox.core.db.base import Base
from ._mixins import IDMixin, TimestampMixin
from ..types import EncryptedString
from ...constants.enums import InviteStatus, UserStatus, UserRoles


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

    status: Mapped[UserStatus] = mapped_column(
        SAEnum(UserStatus),
        nullable=False,
        default=UserStatus.PENDING,
    )

    role: Mapped[UserRoles] = mapped_column(
        SAEnum(Role),
        nullable=False,
        default=UserRoles.DEFAULT,
    )
    tenant: Mapped["Tenant"] = relationship(back_populates="users")
    created_prescriptions: Mapped[list["Prescription"]] = relationship(
        back_populates="created_by"
    )


