"""Repository Invitation."""

from datetime import datetime

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

    async def get_valid_by_email(self, email: str) -> Invitation | None:
        """Recherche une invitation valide par email.

        Parameters
        ----------
        email : str
            Email de l'utilisateur à créer

        Returns
        -------
        Invitation
            Invitation crée.

        Raises
        ------
        HTTPException :
            Si l'objet n'existe pas ou déja dans un tenant, ou déja  une invité"

        """
        async with async_session_local() as session:
            stmt = (
                select(self.model)
                .where(self.model.email == email)
                .where(self.model.expires_at > datetime.now())
                .where(self.model.status == InviteStatus.PENDING)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
