"""Service de gestion des utilisateurs."""

from fastapi import HTTPException

from medbox.core.db.models import User
from medbox.core.db.repositories.user import UserRepository
from medbox.core.services.security import UserContext


class UserService:
    """Service de gestion des utilisateurs."""

    def __init__(self, user_repo: UserRepository | None = None) -> None:
        """Constructeur.

        Parameters
        ----------
        user_repo : UserRepository
            Repository des utilisateurs

        """
        self.user_repo = user_repo or UserRepository()

    async def get_user_from_subject(self, subject_id: str) -> User | None:
        """Charge un utilisateur Medbox via son subject Keycloak (sub).

        Parameters
        ----------
        subject_id : str
            Identifiant du sujet keycloak.

        Returns
        -------
        User
            L'utilisateur si trouvé

        Raises
        ------
        HTTPException :
            Erreur d'intégrité ou si l'utilisateur existe pas.

        """
        user: User | None = await self.user_repo.get_by_subject(subject_id)
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        return user

    async def sync_user_from_identity_provider(self, user_context: UserContext) -> User:
        """Met à jour un utilisateur après l'authentification.

        Parameters
        ----------
        user_context : UserContext
            Informations transmise par le provider d'auth

        Returns
        -------
        User
            Utilisateur créé / mis à jour

        Raises
        ------
        HTTPException
            Si un conflit de création se produit (email déjà existant, etc.).

        """
        return await self.user_repo.update_or_create(
            filters={"keycloak_subject": user_context.subject},
            defaults={
                "email": user_context.email,
                "c_full_name": user_context.full_name,
            },
        )


def get_user_service() -> UserService:
    """Getter du service."""
    return UserService()
