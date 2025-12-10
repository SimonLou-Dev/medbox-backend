"""Router pour la gestion des invitations."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.responses import JSONResponse

from medbox.api.deps.response import ok_response
from medbox.core.constants.enums import UserRoles
from medbox.core.db.models import User
from medbox.core.dto.invitation import (
    ClaimInvitationDTO,
    ResponseInvitationDTO,
    ResponseInvitationWithCodeDTO,
)
from medbox.core.services import (
    CurrentUser,
    TenantInvitSvcDep,
    TenantRightSvcDep,
    UserContext,
    UserSvcDep,
    oauth2_scheme,
)
from medbox.core.services.tenant_right import require_tenant_role

router = APIRouter(prefix="/invite", tags=["invitation"])
admin_router = APIRouter(prefix="/tenant/{tenant_id}/invite", tags=["invitation"])

# ==============================================================================
# Routes
# ==============================================================================


@router.patch("/claim", dependencies=[Security(oauth2_scheme)])
async def accept_invitation(
    body: ClaimInvitationDTO,
    user: CurrentUser,
    tenant_right_svc: TenantRightSvcDep,
    user_svc: UserSvcDep,
    tenant_invite_svc: TenantInvitSvcDep,
) -> JSONResponse:
    """Permet de rejoindre un tenant via le code."""
    user: User = await user_svc.get_user_from_subject(user.subject)
    if await tenant_right_svc.ensure_user_not_in_tenant(user.subject):
        await tenant_invite_svc.claim_invitation(body.code, user)
        return ok_response

    raise HTTPException(status_code="400", detail="Vous êtes déja dans un tenant.")


@admin_router.patch("/{invitation_id}/revoke", dependencies=[Security(oauth2_scheme)])
async def revoke_invitation(
    invitation_id: str,
    _: Annotated[UserContext, Depends(require_tenant_role(UserRoles.TENANT_ADMIN))],
    tenant_invite_svc: TenantInvitSvcDep,
) -> JSONResponse:
    """Permet de forcer l'expiration d'une invitation.

    Nécessite le rôle TENANT_ADMIN.

    Args:
        invitation_id: UUID de l'invitation
        _: Utilisateur authentifié avec rôle admin
        tenant_invite_svc: Service des invitation tenants

    """
    await tenant_invite_svc.expire_invitation(invitation_id)

    return ok_response


@admin_router.post("/{invitation_id}/create", dependencies=[Security(oauth2_scheme)])
async def create_invitation(
    invitation_id: str,
    _: Annotated[UserContext, Depends(require_tenant_role(UserRoles.TENANT_ADMIN))],
    tenant_invite_svc: TenantInvitSvcDep,
) -> ResponseInvitationWithCodeDTO:
    """Permet de forcer l'expiration d'une invitation.

    Nécessite le rôle TENANT_ADMIN.

    Args:
        invitation_id: UUID de l'invitation
        _: Utilisateur authentifié avec rôle admin
        tenant_invite_svc: Service des invitation tenants

    """
    await tenant_invite_svc.expire_invitation(invitation_id)

    return ok_response


@admin_router.get("/", dependencies=[Security(oauth2_scheme)])
async def list_invitations(
    tenant_id: str,
    _: Annotated[UserContext, Depends(require_tenant_role(UserRoles.TENANT_ADMIN))],
    tenant_invite_svc: TenantInvitSvcDep,
) -> list[ResponseInvitationDTO]:
    """Permet de lister les invitation d'un tenant.

    Nécessite le rôle TENANT_ADMIN.

    Args:
        invitation_id: UUID de l'invitation
        _: Utilisateur authentifié avec rôle admin
        tenant_invite_svc: Service des invitation tenants

    """
    await tenant_invite_svc.get_paginated_invitations(tenant_id=tenant_id)
