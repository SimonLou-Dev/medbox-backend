"""Repository pour les utilisateurs."""

from sqlalchemy import select

from medbox.core.db.models.user import User
from medbox.core.db.repositories.base import BaseRepository
from medbox.core.db.session import async_session_local


class UserRepository(BaseRepository[User]):
    """Repository utilisateur."""

    def __init__(self) -> None:
        """Constructeur."""
        super().__init__(User)

    async def get_by_subject(self, subject_id: str) -> User | None:
        """Récupère un enregistrement via son identifiant.

        Parameters
        ----------
        subject_id : str
            Identifiant du sujet keycloak.

        Returns
        -------
        Optional[ModelType]
            L'objet si trouvé, sinon None.

        """
        async with async_session_local() as session:
            stmt = select(self.model).where(self.model.keycloak_subject == subject_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
