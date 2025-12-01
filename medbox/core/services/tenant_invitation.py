import secrets
import string
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import HTTPException

from medbox.core.db.models.invitation import Invitation
from medbox.core.db.models.user import User
from medbox.core.db.repositories.invitation import InvitationRepository
from medbox.core.db.repositories.tenant import TenantRepository
from medbox.core.db.repositories.user import UserRepository
from medbox.core.tasks import expire_invitation


class TenantInvitationService:
    """Service de gestion des invitation sur les tenants."""

    def __init__(
        self,
        user_repo: UserRepository,
        tenant_repo: TenantRepository,
        invite_repo: InvitationRepository,
    ) -> None:
        """Constructeur.

        Parameters
        ----------
        tenant_repo : TenantRepository
            Repository des tenants
        user_repo : UserRepository
            Repository des utilisateurs
        invite_repo: InvitationRepository
            Repository des invitation

        """
        self.user_repo = user_repo
        self.tenant_repo = tenant_repo
        self.invite_repo = invite_repo

    async def add_user_to_tenant(self, user_id: UUID, tenant_id: str) -> User:
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

    async def invite_user_to_tenant(
        self,
        sender: User,
        target_mail: str,
        tenant_id: UUID,
    ) -> Invitation:
        """Créé une invitation permettant de joindre un utilisateur.

        Parameters
        ----------
        sender : User
            Identifiant de l'utilisateur qui a envoyé l'invitation
        target_mail : str
            Email de l'utilisateur à créer
        tenant_id : UUID
            Tenant dans lequel ajouter l'utilisateur

        Returns
        -------
        Invitation
            Invitation crée.

        Raises
        ------
        HTTPException :
            Si l'objet n'existe pas ou déja dans un tenant, ou déja  une invité"

        """
        if await self.user_repo.exists(email=target_mail):
            raise HTTPException(
                status_code=400,
                detail="L'utilisateur avec cette addresse mail existe déja",
            )

        if await self.invite_repo.get_valid_by_email(target_mail):
            raise HTTPException(
                status_code=400,
                detail="L'utilisateur a déja une invitation en cours.",
            )

        expires = datetime.now() + timedelta(hours=1)

        invite = Invitation(
            tenant_id=tenant_id,
            email=target_mail,
            code=await self._generate_invitation_code(),
            expires_at=expires,
            sended_by_user_id=sender.id,
        )

        invite = await self.invite_repo.add(invite)

        await expire_invitation.send_with_options(
            args=[str(invite.id)],
            delay=3600 * 1000,  # Dramatiq prend les ms
        )

        return invite

    async def _generate_invitation_code(self) -> str:
        """Créé un code d'invitation unique.

        Returns
        -------
        code
            Code à 6 chiffres

        """
        while True:
            code: str = "".join(secrets.choice(string.digits) for _ in range(6))
            if not (code := await self.invite_repo.exists({"code": code})):
                return code
