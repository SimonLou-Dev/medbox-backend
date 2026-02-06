import secrets
import string
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import HTTPException

from medbox.core.constants.enums import InviteStatus
from medbox.core.db.models.invitation import Invitation
from medbox.core.db.models.user import User
from medbox.core.db.repositories.invitation import InvitationRepository
from medbox.core.db.repositories.tenant import TenantRepository
from medbox.core.db.repositories.user import UserRepository
from medbox.core.dto.invitation import ResponseInvitationDTO
from medbox.core.dto.page import PaginatedDTO
from medbox.core.exceptions import ModelNotFoundError
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
        # NOTE: Check désactivé pour permettre d'inviter des utilisateurs existants
        # if await self.user_repo.exists({"email": target_mail}):
        #     raise HTTPException(
        #         status_code=400,
        #         detail="L'utilisateur avec cette addresse mail existe déja",
        #     )

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

        expire_invitation.send_with_options(
            args=[str(invite.id)],
            delay=3600 * 1000,  # Dramatiq prend les ms
        )

        return invite

    async def revoke_invitation(self, invitation_id: UUID) -> None:
        """Supprime une invitation.

        Parameters
        ----------
        invitation_id : UUID
            Identifiant de l'invitation cible

        Returns
        -------
        None

        Raises
        ------
        HTTPException :
            Si l'invitation n'existe pas"

        """
        if not await self.invite_repo.exists({"id": invitation_id}):
            raise HTTPException(
                status_code=404,
                detail="L'invitation n'existe ps",
            )

        await self.invite_repo.update(
            m_id=invitation_id,
            values={"status": InviteStatus.CANCELED},
        )

    async def claim_invitation(self, code: str, user: User) -> bool:
        """Supprime une invitation.

        Parameters
        ----------
        code : str
            Code de l'invitation
        user: User
            Utilisateur qui demande à rejoindre le tenant

        Returns
        -------
        Boolean
            True si accepté, False si refusé

        Raises
        ------
        HTTPException :
            Si l'invitation n'existe pas

        """
        invitation = await self.invite_repo.get_by_code(code)

        if not invitation or invitation.email != user.email:
            raise HTTPException(
                status_code=404,
                detail="Le code saisi est invalide",
            )

        if invitation.status is not InviteStatus.PENDING:
            raise HTTPException(
                status_code=404,
                detail="L'invitation n'est plus valide",
            )

        # On met le user dans le TENANT
        await self.add_user_to_tenant(user_id=user.id, tenant_id=invitation.tenant_id)

        # On ferme l'invitation
        await self.invite_repo.update(
            invitation.id,
            {
                "claimed_by_user_id": user.id,
                "status": InviteStatus.CLAIMED,
            },
        )
        return True

    async def expire_invitation(self, invitation_id: UUID) -> bool:
        """Permet de mettre l'invitation au status EXPIRE.

        Parameters
        ----------
        invitation_id: UUID
            Identifiant de l'invitation à expirer

        Returns
        -------
        Boolean
            True si accepté, False si refusé

        Raises
        ------
        HTTPException :
            Si l'invitation n'existe pas

        """
        invitation = await self.invite_repo.get(invitation_id)

        if not invitation:
            raise ModelNotFoundError(
                "invitation",
                str(invitation_id),
            )

        # On ferme l'invitation
        await self.invite_repo.update(
            invitation.id,
            {
                "status": InviteStatus.EXPIRED,
            },
        )

    async def _generate_invitation_code(self) -> str:
        """Créé un code d'invitation unique.

        Returns
        -------
        code
            Code à 6 chiffres

        """
        while True:
            code: str = "".join(secrets.choice(string.digits) for _ in range(6))
            if not await self.invite_repo.exists({"code": code}):
                return code

    async def get_paginated_invitations(
        self,
        tenant_id: str,
    ) -> PaginatedDTO[ResponseInvitationDTO]:
        """List les invitations d'un tenant.

        Parameters
        ----------
        tenant_id : UUID
            Tenant dans lequel ajouter l'utilisateur

        Returns
        -------
        list[ResponseInvitationDTO]
            Liste des invitation

        Raises
        ------
        HTTPException :
            Si l'objet n'existe pas.

        """
        paginated = await self.invite_repo.paginate(filters={"tenant_id": tenant_id})

        return PaginatedDTO.to_dto_page(paginated, ResponseInvitationDTO)
