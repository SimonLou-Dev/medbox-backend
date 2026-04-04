"""Service de gestion des droits sur les tenants."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, Response, status

from medbox.core.constants.enums import UserRoles, UserStatus
from medbox.core.db.models.user import User
from medbox.core.db.repositories.tenant import TenantRepository
from medbox.core.db.repositories.user import UserRepository
from medbox.core.services.security import (
    SecurityService,
    UserContext,
    get_security_service,
)


class TenantRightService:
    """Service de gestion des droits sur les tenants."""

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

    async def set_user_role(self, user_id: UUID, role: UserRoles) -> User:
        """Ajoute l'utilisateur  dans le tenant.

        Parameters
        ----------
        user_id : UUID
            Identifiant de l'utilisateur
        role : UserRoles
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

        # On pourrait créer une invitation ici, mais si tu veux assigner direct :
        return await self.user_repo.update(
            user_id,
            values={"role": role},
        )

    async def ensure_user_in_tenant(self, user_sub: str, tenant_id: UUID) -> bool:
        """Vérifie que l'utilisateur est dans le tenant.

        Parameters
        ----------
        user_sub : sub
            Identifiant keycloak de l'utilisateur
        tenant_id : UUID
            Tenant cible

        Returns
        -------
        bool
            True si le  user est bien dans le tenant.

        Raises
        ------
        HTTPException :
            Si l'objet n'existe pas.

        """
        return await self.user_repo.exists(
            {
                "keycloak_subject": user_sub,
                "tenant_id": tenant_id,
                "status": UserStatus.ACTIVE,
            },
        )

    async def ensure_user_not_in_tenant(self, user_sub: str) -> bool:
        """Vérifie que l'utilisateur n'est pas dans un tenant.

        Parameters
        ----------
        user_sub : sub
            Identifiant keycloak de l'utilisateur

        Returns
        -------
        bool
            True si le  user est bien dans le tenant.

        Raises
        ------
        HTTPException :
            Si l'objet n'existe pas.

        """
        return await self.user_repo.exists(
            {
                "keycloak_subject": user_sub,
                "tenant_id": None,
            },
        )

    async def ensure_user_in_tenant_has_role(
        self,
        user_sub: str,
        tenant_id: UUID,
        role: UserRoles,
    ) -> bool:
        """Vérifie que l'utilisateur est dans le tenant.

        Parameters
        ----------
        user_sub : sub
            Identifiant keycloak de l'utilisateur
        tenant_id : UUID
            Tenant cible
        role: UserRoles
            Rôle réquis

        Returns
        -------
        bool
            True si le  user est bien dans le tenant.

        Raises
        ------
        HTTPException :
            Si l'objet n'existe pas.

        """
        return await self.user_repo.exists(
            {
                "keycloak_subject": user_sub,
                "tenant_id": tenant_id,
                "status": UserStatus.ACTIVE,
                "role": role,
            },
        )

    async def ensure_user_in_tenant_or_fail(
        self,
        user_sub: str,
        tenant_id: UUID,
    ) -> bool:
        """Vérifie que l'utilisateur est dans le tenant.

        Parameters
        ----------
        user_sub : sub
            Identifiant keycloak de l'utilisateur
        tenant_id : UUID
            Tenant cible

        Returns
        -------
        bool
            True si le  user est bien dans le tenant.

        Raises
        ------
        HTTPException :
            Si non authorisé

        """
        if not await self.ensure_user_in_tenant(user_sub, tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès non authorisé en dehors du tenant",
            )
        return True

    async def ensure_user_in_tenant_has_role_or_fail(
        self,
        user_sub: str,
        tenant_id: UUID,
        role: UserRoles,
    ) -> bool:
        """Vérifie que l'utilisateur est dans le tenant.

        Parameters
        ----------
        user_sub : sub
            Identifiant keycloak de l'utilisateur
        tenant_id : UUID
            Tenant cible
        role: UserRoles
            Rôle réquis

        Returns
        -------
        bool
            True si le  user est bien dans le tenant.

        Raises
        ------
        HTTPException :
            Si non authorisé

        """
        if not await self.ensure_user_in_tenant_has_role(user_sub, tenant_id, role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès non authorisé pour ce rôle",
            )
        return True


def get_tenant_right_service() -> TenantRightService:
    """Dependency pour obtenir le service de sécurité."""
    return TenantRightService(
        UserRepository(),
        TenantRepository(),
    )


async def require_user_in_tenant(
    tenant_id: UUID,
    request: Request,
    response: Response,
    security: Annotated[SecurityService, Depends(get_security_service)],
    tenant_right: Annotated[TenantRightService, Depends(get_tenant_right_service)],
) -> UserContext:
    """Vérifie que l'utilisateur courant est dans le tenant t_id."""
    user = await security.get_current_user(request, response)

    is_valid = await tenant_right.ensure_user_in_tenant(
        user_id=user.subject,
        tenant_id=tenant_id,
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès non authorisé en dehors du tenant",
        )

    return user


async def require_user_in_tenant_with_role(
    tenant_id: UUID,
    role: UserRoles,
    request: Request,
    response: Response,
    security: Annotated[SecurityService, Depends(get_security_service)],
    tenant_right: Annotated[TenantRightService, Depends(get_tenant_right_service)],
) -> UserContext:
    """Vérifie que l'utilisateur courant est dans le tenant ET possède un rôle."""
    user = await security.get_current_user(request, response)

    allowed = await tenant_right.ensure_user_in_tenant_has_role(
        user_sub=user.subject,
        tenant_id=tenant_id,
        role=role,
    )

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas le rôle réquis",
        )

    return user


def require_tenant_role(role: UserRoles):
    """Fabrique une dependency qui vérifie un rôle spécifique dans un tenant."""

    async def dependency(
        tenant_id: UUID,
        request: Request,
        response: Response,
        security: Annotated[SecurityService, Depends(get_security_service)],
        tenant_right: Annotated[TenantRightService, Depends(get_tenant_right_service)],
    ) -> UserContext:
        user = await security.get_current_user(request, response)

        allowed = await tenant_right.ensure_user_in_tenant_has_role(
            user_sub=user.subject,
            tenant_id=tenant_id,
            role=role,
        )

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous n'avez pas le rôle réquis",
            )
        return user

    return dependency


def require_superadmin():
    """Dependency qui vérifie que l'utilisateur a le rôle super_admin dans ses claims Keycloak."""

    async def dependency(
        request: Request,
        response: Response,
        security: Annotated[SecurityService, Depends(get_security_service)],
    ) -> UserContext:
        user = await security.get_current_user(request, response)

        all_roles: list[str] = []
        # Realm roles (flat mapper ou realm_access.roles)
        all_roles += user.claims.get("realm_roles") or []
        all_roles += user.claims.get("realm_access", {}).get("roles", [])
        # Client roles (resource_access.<client>.roles)
        for client_access in user.claims.get("resource_access", {}).values():
            all_roles += client_access.get("roles", [])

        if UserRoles.SUPER_ADMIN.value not in all_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès réservé aux super-admins",
            )
        return user

    return dependency
