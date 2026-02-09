"""Repository Invitation."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from medbox.core.constants.enums import InviteStatus
from medbox.core.db.models.invitation import Invitation
from medbox.core.db.repositories.base import BaseRepository
from medbox.core.db.session import async_session_local


class InvitationRepository(BaseRepository[Invitation]):
    """Repository Invitation."""

    def __init__(self) -> None:
        """Constructeur."""
        super().__init__(Invitation)

    async def get_active_by_tenant(self, tenant_id: UUID) -> Invitation | None:
        """Recherche le code d'invitation actif (PENDING, non expiré) pour un tenant.

        Parameters
        ----------
        tenant_id : UUID
            Identifiant du tenant

        Returns
        -------
        Invitation | None
            L'invitation active ou None

        """
        async with async_session_local() as session:
            stmt = (
                select(self.model)
                .where(self.model.tenant_id == tenant_id)
                .where(self.model.expires_at > datetime.now())
                .where(self.model.status == InviteStatus.PENDING)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Invitation | None:
        """Recherche une invitation via son code.

        Parameters
        ----------
        code : str
            Code à saisir par l'utilisateur

        Returns
        -------
        Invitation | None
            Invitation trouvée ou None

        """
        async with async_session_local() as session:
            stmt = select(self.model).where(self.model.code == code)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
