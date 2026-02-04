"""Router pour la gestion des invitations."""

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from medbox.api.deps.response import ok_response
from medbox.core.constants.enums import UserRoles
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
)
from medbox.core.services.tenant_right import require_tenant_role

if TYPE_CHECKING:
    from medbox.core.db.models import User

router = APIRouter(prefix="/invite", tags=["invitation"])
admin_router = APIRouter(prefix="/tenant/{tenant_id}/invite", tags=["invitation"])

# ==============================================================================
# Routes
# ==============================================================================


@router.patch("/claim")
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


@admin_router.patch("/{invitation_id}/revoke")
async def revoke_invitation(
    invitation_id: str,
    _: Annotated[
        UserContext,
        Depends(require_tenant_role(UserRoles.TENANT_ADMIN)),
    ],
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


@admin_router.post("/send")
async def send_invitation(
    tenant_id: str,
    target_email: str,
    user_ctx: Annotated[
        UserContext,
        Depends(require_tenant_role(UserRoles.TENANT_ADMIN)),
    ],
    tenant_invite_svc: TenantInvitSvcDep,
    user_svc: UserSvcDep,
) -> ResponseInvitationWithCodeDTO:
    """Envoie une invitation pour joindre le tenant.

    Nécessite le rôle TENANT_ADMIN.
    Route: POST /api/v1/tenant/{tenant_id}/invite/send

    Args:
        tenant_id: UUID du tenant
        target_email: Email de la personne à inviter
        user_ctx: Utilisateur authentifié avec rôle admin
        tenant_invite_svc: Service des invitation tenants
        user_svc: Service utilisateurs

    Returns:
        ResponseInvitationWithCodeDTO: Code d'invitation généré

    Raises:
        HTTPException: Si l'email existe déjà ou invitation en cours

    """
    sender = await user_svc.get_user_from_subject(user_ctx.subject)
    invitation = await tenant_invite_svc.invite_user_to_tenant(
        sender=sender,
        target_mail=target_email,
        tenant_id=tenant_id,
    )
    return ResponseInvitationWithCodeDTO(code=invitation.code)


@admin_router.get("/")
async def list_invitations(
    tenant_id: str,
    _: Annotated[
        UserContext,
        Depends(require_tenant_role(UserRoles.TENANT_ADMIN)),
    ],
    tenant_invite_svc: TenantInvitSvcDep,
) -> list[ResponseInvitationDTO]:
    """Lister les invitations d'un tenant.

    Nécessite le rôle TENANT_ADMIN.

    Args:
        tenant_id: UUID du tenant
        _: Utilisateur authentifié avec rôle admin
        tenant_invite_svc: Service des invitation tenants

    Returns:
        list[ResponseInvitationDTO]: Liste des invitations du tenant

    """
    await tenant_invite_svc.get_paginated_invitations(tenant_id=tenant_id)
