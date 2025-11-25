import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medbox.core.db.base import Base
from ._mixins import IDMixin, TimestampMixin
from ..types import EncryptedString
from ...constants.enums import InviteStatus


class Invitation(Base, IDMixin, TimestampMixin):
    """
    Utilisateur logique Medbox (lié à Keycloak via subject_id).
    Pas de mot de passe ici, tout est externalisé.
    """

    __tablename__ = 'invitations'

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        doc="Email ciblé par l'invitation",
    )

    code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        doc="Code unique à saisir par l'utilisateur",
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[InviteStatus] = mapped_column(
        SAEnum(InviteStatus),
        nullable=False,
        default=InviteStatus.PENDING,
    )

    claimed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="User qui a utilisé cette invitation, si applicable",
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="invitations")
    claimed_by_user: Mapped["User | None"] = relationship()