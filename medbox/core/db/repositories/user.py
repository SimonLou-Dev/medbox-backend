"""Repository pour les utilisateurs."""

from collections.abc import Sequence

from fastapi import HTTPException
from sqlalchemy import select

from medbox.core.db.models.user import User
from medbox.core.db.repositories.base import BaseRepository
from medbox.core.db.session import async_session_local


class UserRepository(BaseRepository[User]):
    """Repository utilisateur."""

    def __init__(self, tenant_id: str | None = None) -> None:
        """Constructeur.

        Parameters
        ----------
        tenant_id : str | None
            ID du tenant pour scoper les données (optionnel).

        """
        super().__init__(User)
        self.tenant_id = tenant_id

    async def list(self) -> Sequence[User]:
        """Renvoie l'ensemble des utilisateurs, scoped by tenant si fourni.

        Returns
        -------
        Sequence[User]
            Liste des utilisateurs.

        """
        async with async_session_local() as session:
            stmt = select(self.model)

            # Scope by tenant if provided
            if self.tenant_id:
                stmt = stmt.where(self.model.tenant_id == self.tenant_id)

            result = await session.execute(stmt)
            return result.scalars().all()

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

            # Scope by tenant if provided
            if self.tenant_id:
                stmt = stmt.where(self.model.tenant_id == self.tenant_id)

            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_subject_or_fail(self, subject_id: str) -> User | None:
        """Récupère un enregistrement via son identifiant.

        Parameters
        ----------
        subject_id : str
            Identifiant du sujet keycloak.

        Returns
        -------
        ModelType
            L'objet

        Raise
        ------
        HTTPException
            Utilisateur non trouvé


        """
        async with async_session_local() as session:
            stmt = select(self.model).where(self.model.keycloak_subject == subject_id)
            result = await session.execute(stmt)
            usr = result.scalar_one_or_none()

            if not usr:
                raise HTTPException(
                    status_code=404,
                    detail="Impossible de trouver l'utilisateur",
                )
            return usr
