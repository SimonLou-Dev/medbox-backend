"""Service de gestion des tenant."""

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException

from medbox.core.constants.enums import UserRoles, UserStatus
from medbox.core.db.models.tenant import Tenant
from medbox.core.db.models.user import User
from medbox.core.db.repositories.tenant import TenantRepository
from medbox.core.db.repositories.user import UserRepository
from medbox.core.dto.tenant import TenantRequest, TenantResponse
from medbox.core.services.security import UserContext

if TYPE_CHECKING:
    from medbox.core.services.tenant_invitation import TenantInvitationService
    from medbox.core.services.tenant_right import TenantRightService


class TenantService:
    """Service de gestion des tenant."""

    def __init__(
        self,
        tenant_invit_svc: "TenantInvitationService",
        tenant_right_svc: "TenantRightService",
        tenant_repo: TenantRepository | None = None,
        user_repo: UserRepository | None = None,
    ) -> None:
        """Constructeur.

        Parameters
        ----------
        tenant_repo : TenantRepository
            Repository des tenants
        user_repo : UserRepository
            Repository des utilisateurs
        tenant_invit_svc : TenantInvitationService
            Service des invitations tenant
        tenant_right_svc : TenantRightService
            Service des droits tenant

        """
        self.tenant_repo = tenant_repo or TenantRepository()
        self.user_repo = user_repo or UserRepository()
        self.tenant_invit_svc = tenant_invit_svc
        self.tenant_right_svc = tenant_right_svc

    async def list(self) -> list[Tenant]:
        """List les tenants existants.

        Returns
        -------
        list[Tenant]
            Liste des tenants existant

        """

    async def get(self, m_id: UUID) -> TenantResponse:
        """List les tenants existants.

        Returns
        -------
        Tenant
            Tenant demandé

        """
        return await self.tenant_repo.get_with_counts(m_id)

    async def update(self, m_id: UUID, body: TenantRequest) -> Tenant:
        """Met à jour un tenant.

        Parameters
        ----------
        m_id : UUID
            Identifiant du tenant
        body : TenantRequest
            Nouvelles données

        Returns
        -------
        Tenant
            Tenant mis à jour

        Raises
        ------
        HTTPException :
            Si le tenant n'existe pas.

        """
        tenant = await self.tenant_repo.get(m_id)
        if tenant is None:
            raise HTTPException(status_code=404, detail="Tenant introuvable")

        return await self.tenant_repo.update(m_id, {"name": body.name})

    async def delete(self, m_id: UUID) -> bool:
        """Supprime le tenant.

        Returns
        -------
        bool
            True si supprimé

        Raises
        ------
        HTTPException :
            Si le tenant n'existe pas.

        """
        tenant = await self.tenant_repo.get(m_id, ["users"])
        if tenant is None:
            raise HTTPException(status_code=404, detail="Tenant introuvable")

        for user in tenant.users:
            await self.user_repo.update(
                user.id,
                {
                    "role": UserRoles.DEFAULT,
                    "status": UserStatus.PENDING,
                    "tenant_id": None,
                },
            )
        await self.tenant_repo.delete(m_id)

        return True

    async def leave_tenant(self, user_subject: str) -> None:
        """Permet a un utilisateur non-admin de quitter son tenant.

        Parameters
        ----------
        user_subject : str
            Subject Keycloak de l'utilisateur

        Raises
        ------
        HTTPException :
            Si l'utilisateur n'est pas dans un tenant ou est admin.

        """
        user = await self.user_repo.get_by_subject_or_fail(user_subject)

        if user.tenant_id is None:
            raise HTTPException(
                status_code=400,
                detail="Vous n'appartenez a aucun etablissement",
            )

        if user.role == UserRoles.TENANT_ADMIN:
            raise HTTPException(
                status_code=403,
                detail="Un administrateur ne peut pas quitter l'etablissement",
            )

        await self.user_repo.update(
            user.id,
            {
                "tenant_id": None,
                "role": UserRoles.DEFAULT,
                "status": UserStatus.PENDING,
            },
        )

    async def create(self, body: TenantRequest, usr_ctx: UserContext) -> (Tenant, User):
        """Crée un nouveau tenant.

        Returns
        -------
        Tenant
            Tenant créé
        User
            Administrateur du tenant

        Raises
        ------
        HTTPException :
            Si l'utilisateur appartient déjà à un tenant.

        """
        # Vérifier que l'utilisateur n'appartient pas déjà à un tenant
        user = await self.user_repo.get_by_subject_or_fail(usr_ctx.subject)
        if user.tenant_id is not None:
            raise HTTPException(
                status_code=400,
                detail="Vous appartenez déjà à un établissement.",
            )

        tenant = Tenant(name=body.name)
        tenant = await self.tenant_repo.add(tenant)

        user = await self.tenant_invit_svc.add_user_to_tenant(user.id, tenant.id)
        user = await self.tenant_right_svc.set_user_role(
            user.id,
            UserRoles.TENANT_ADMIN,
        )
        user = await self.user_repo.update(user.id, {"status": UserStatus.ACTIVE})

        return tenant, user
