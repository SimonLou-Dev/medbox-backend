import secrets
import string
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException

from medbox.core.constants.enums import InviteStatus, UserStatus
from medbox.core.db.models.invitation import Invitation
from medbox.core.db.models.user import User
from medbox.core.db.repositories.invitation import InvitationRepository
from medbox.core.db.repositories.tenant import TenantRepository
from medbox.core.db.repositories.user import UserRepository
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

        return await self.user_repo.update(
            user_id,
            values={"tenant_id": tenant_id},
        )

    async def generate_invite_code(
        self,
        sender: User,
        tenant_id: UUID,
    ) -> Invitation:
        """Génère un code d'invitation temporaire pour rejoindre le tenant.

        Expire les codes actifs précédents avant d'en créer un nouveau
        (1 seul code actif par tenant). Durée de validité : 10 minutes.

        Parameters
        ----------
        sender : User
            Utilisateur qui génère le code
        tenant_id : UUID
            Tenant pour lequel générer le code

        Returns
        -------
        Invitation
            Invitation créée avec le code.

        """
        # Expire le code actif précédent s'il existe
        active = await self.invite_repo.get_active_by_tenant(tenant_id)
        if active:
            await self.invite_repo.update(
                active.id,
                {"status": InviteStatus.EXPIRED},
            )

        expires = datetime.now(tz=UTC) + timedelta(minutes=10)

        invite = Invitation(
            tenant_id=tenant_id,
            code=await self._generate_invitation_code(),
            expires_at=expires,
            sended_by_user_id=sender.id,
        )

        invite = await self.invite_repo.add(invite)

        expire_invitation.apply_async(
            args=[str(invite.id)],
            countdown=600,  # 10 minutes en secondes
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
            Si l'invitation n'existe pas

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
        """Permet à un utilisateur de rejoindre un tenant via un code d'invitation.

        Parameters
        ----------
        code : str
            Code de l'invitation
        user: User
            Utilisateur qui demande à rejoindre le tenant

        Returns
        -------
        Boolean
            True si accepté

        Raises
        ------
        HTTPException :
            Si le code est invalide ou l'invitation n'est plus valide

        """
        invitation = await self.invite_repo.get_by_code(code)

        if not invitation:
            raise HTTPException(
                status_code=404,
                detail="Le code saisi est invalide",
            )

        if invitation.status is not InviteStatus.PENDING:
            raise HTTPException(
                status_code=400,
                detail="L'invitation n'est plus valide",
            )

        expires_at = invitation.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < datetime.now(tz=UTC):
            raise HTTPException(
                status_code=400,
                detail="L'invitation a expiré",
            )

        # On met le user dans le TENANT et on l'active
        await self.add_user_to_tenant(user_id=user.id, tenant_id=invitation.tenant_id)
        await self.user_repo.update(user.id, {"status": UserStatus.ACTIVE})

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

    async def get_active_code(self, tenant_id: UUID) -> Invitation | None:
        """Retourne le code d'invitation actif du tenant.

        Parameters
        ----------
        tenant_id : UUID
            Identifiant du tenant

        Returns
        -------
        Invitation | None
            L'invitation active ou None

        """
        return await self.invite_repo.get_active_by_tenant(tenant_id)

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
