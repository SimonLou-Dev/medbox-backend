"""Service de gestion des tenant."""

from uuid import UUID

from medbox.core.constants.enums import UserRoles, UserStatus
from medbox.core.db.models.tenant import Tenant
from medbox.core.db.models.user import User
from medbox.core.db.repositories.tenant import TenantRepository
from medbox.core.db.repositories.user import UserRepository
from medbox.core.dto.tenant import TenantRequest, TenantResponse
from medbox.core.services.security import UserContext


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

    async def delete(self, m_id: UUID) -> bool:
        """Supprime le tenant.

        Returns
        -------
        Tenant
            Tenant demandé

        """
        tenant = await self.tenant_repo.get(m_id, ["users"])
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

    async def create(self, body: TenantRequest, usr_ctx: UserContext) -> (Tenant, User):
        """List les tenants existants.

        Returns
        -------
        Tenant
            Tenant demandé
        User
            Administrateur du tenant

        """
        tenant = Tenant(name=body.name)

        tenant = await self.tenant_repo.add(tenant)
        user = await self.user_repo.get_by_subject_or_fail(usr_ctx.subject)
        user = await self.tenant_invit_svc.add_user_to_tenant(user.id, tenant.id)
        user = await self.tenant_right_svc.set_user_role(
            user.id,
            UserRoles.TENANT_ADMIN,
        )
        user = await self.user_repo.update(user.id, {"status": UserStatus.ACTIVE})

        return tenant, user
