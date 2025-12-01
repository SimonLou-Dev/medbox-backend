"""Définition du modèle  d'une Invitation."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medbox.core.constants.enums import InviteStatus
from medbox.core.db.base import Base
from medbox.core.db.models._mixins import IDMixin, TimestampMixin

if TYPE_CHECKING:
    from medbox.core.db.models.tenant import Tenant
    from medbox.core.db.models.user import User


class Invitation(Base, IDMixin, TimestampMixin):
    """Invitation d'un  utilisateur dans un tenant."""

    __tablename__ = "invitations"

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

    sended_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        doc="User qui a envoyé cette invitation, si applicable",
    )

    claimed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="User qui a utilisé cette invitation, si applicable",
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="invitations")
    claimed_by_user: Mapped["User | None"] = relationship()
    sended_by_user: Mapped["User"] = relationship()
