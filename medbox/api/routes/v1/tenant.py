"""Router pour la gestion des tenants."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Security, status

from medbox.core.constants.enums import UserRoles
from medbox.core.dto.tenant import TenantRequest, TenantResponse
from medbox.core.services import (
    CurrentUser,
    TenantRightSvcDep,
    TenantSvcDep,
    UserContext,
    oauth2_scheme,
)
from medbox.core.services.tenant_right import require_tenant_role

router = APIRouter(prefix="/tenant", tags=["Tenant"])

# ==============================================================================
# Routes
# ==============================================================================


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(oauth2_scheme)],
)
async def create_tenant(
    body: TenantRequest,
    user: CurrentUser,
    tenant_svc: TenantSvcDep,
) -> TenantResponse:
    """Crée un nouveau tenant.

    L'utilisateur authentifié devient automatiquement admin du tenant.

    Args:
        body: Données du tenant à créer
        user: Utilisateur authentifié
        tenant_svc: Service des tenants

    Returns:
        Tenant créé avec informations de l'admin

    """
    tenant, _ = await tenant_svc.create(body, user)

    return await tenant_svc.get(tenant.id)


@router.get("/{tenant_id}", dependencies=[Security(oauth2_scheme)])
async def get_tenant(
    tenant_id: UUID,
    tenant_right_svc: TenantRightSvcDep,
    user: CurrentUser,
    tenant_svc: TenantSvcDep,
) -> TenantResponse:
    """Récupère les informations d'un tenant.

    Nécessite d'appartenir au tenant.

    Args:
        tenant_id: UUID du tenant
        user: Utilisateur authentifié (vérifié via dependency)
        tenant_svc: Service des tenants
        tenant_right_svc: Service des droits des tenants

    Returns:
        Informations du tenant

    """
    await tenant_right_svc.ensure_user_in_tenant_or_fail(user.subject, tenant_id)
    tenant = await tenant_svc.get(tenant_id)
    return TenantResponse.model_validate(tenant)


@router.put("/{tenant_id}", dependencies=[Security(oauth2_scheme)])
async def update_tenant(
    tenant_id: UUID,
    body: TenantRequest,
    tenant_right_svc: TenantRightSvcDep,
    user: CurrentUser,
    tenant_svc: TenantSvcDep,
) -> TenantResponse:
    """Met à jour un tenant.

    Nécessite le rôle TENANT_ADMIN.

    Args:
        tenant_id: UUID du tenant
        body: Nouvelles données
        user: Utilisateur authentifié avec rôle admin
        tenant_svc: Service des tenants
        tenant_right_svc: Service des droits des tenants

    Returns:
        Tenant mis à jour

    """
    await tenant_right_svc.ensure_user_in_tenant_has_role_or_fail(
        user.subject,
        tenant_id,
        UserRoles.TENANT_ADMIN,
    )
    tenant = await tenant_svc.update(tenant_id, body)
    return TenantResponse.model_validate(tenant)


@router.delete(
    "/{tenant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Security(oauth2_scheme)],
)
async def delete_tenant(
    tenant_id: UUID,
    _: Annotated[UserContext, Depends(require_tenant_role(UserRoles.TENANT_ADMIN))],
    tenant_svc: TenantSvcDep,
) -> None:
    """Supprime un tenant.

    Nécessite le rôle TENANT_ADMIN.

    Args:
        tenant_id: UUID du tenant
        user: Utilisateur authentifié avec rôle admin
        tenant_svc: Service des tenants

    """
    await tenant_svc.delete(tenant_id)
