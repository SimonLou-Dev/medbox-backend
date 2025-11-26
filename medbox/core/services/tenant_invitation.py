from uuid import UUID

from fastapi import HTTPException

from medbox.core.db.models.user import User
from medbox.core.db.repositories.tenant import TenantRepository
from medbox.core.db.repositories.user import UserRepository


class TenantInvitationService:
    """Service de gestion des invitation sur les tenants."""

    def __init__(
        self,
        user_repo: UserRepository,
        tenant_repo: TenantRepository,
    ) -> None:
        """Constructeur.

        Parameters
        ----------
        tenant_repo : TenantRepository
            Repository des tenants
        user_repo : UserRepository
            Repository des utilisateurs

        """
        self.user_repo = user_repo
        self.tenant_repo = tenant_repo

    async def add_user_to_tenant(self, user_id: UUID, tenant_id: UUID) -> User:
        """Ajoute l'utilisateur  dans le tenant.

        Parameters
        ----------
        user_id : UUID
            Identifiant de l'utilisateur
        tenant_id : UUID
            Tenant dans lequel ajouter l'utilisateur

        Returns
        -------
        User
            Utilisateur à jour.

        Raises
        ------
        HTTPException :
            Si l'objet n'existe pas.

        """
        user = await self.user_repo.get(user_id)

        if not user:
            raise HTTPException(404, "Utilisateur introuvable")

        if user.tenant_id is not None:
            raise HTTPException(
                status_code=400,
                detail="L'utilisateur est déjà dans un tenant.",
            )

        # On pourrait créer une invitation ici, mais si tu veux assigner direct :
        return await self.user_repo.update(
            user_id,
            values={"tenant_id": tenant_id},
        )
