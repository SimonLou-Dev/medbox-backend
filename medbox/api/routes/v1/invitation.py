"""Router pour la gestion des invitations."""

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from medbox.api.deps.response import ok_response
from medbox.core.constants.enums import UserRoles
from medbox.core.dto.invitation import (
    ClaimInvitationDTO,
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
    subject = user.subject
    db_user: User = await user_svc.get_user_from_subject(subject)
    if await tenant_right_svc.ensure_user_not_in_tenant(subject):
        await tenant_invite_svc.claim_invitation(body.code, db_user)
        return ok_response

    raise HTTPException(status_code="400", detail="Vous êtes déja dans un tenant.")


@admin_router.post("/generate")
async def generate_invite_code(
    tenant_id: str,
    user_ctx: Annotated[
        UserContext,
        Depends(require_tenant_role(UserRoles.TENANT_ADMIN)),
    ],
    tenant_invite_svc: TenantInvitSvcDep,
    user_svc: UserSvcDep,
) -> ResponseInvitationWithCodeDTO:
    """Génère un code d'invitation temporaire (10 min, usage unique).

    Nécessite le rôle TENANT_ADMIN.
    Route: POST /api/v1/tenant/{tenant_id}/invite/generate

    """
    sender = await user_svc.get_user_from_subject(user_ctx.subject)
    invitation = await tenant_invite_svc.generate_invite_code(
        sender=sender,
        tenant_id=tenant_id,
    )
    return ResponseInvitationWithCodeDTO(
        code=invitation.code,
        expires_at=invitation.expires_at,
    )


@admin_router.get("/active")
async def get_active_code(
    tenant_id: str,
    _: Annotated[
        UserContext,
        Depends(require_tenant_role(UserRoles.TENANT_ADMIN)),
    ],
    tenant_invite_svc: TenantInvitSvcDep,
) -> ResponseInvitationWithCodeDTO | None:
    """Retourne le code d'invitation actif du tenant ou null.

    Nécessite le rôle TENANT_ADMIN.
    Route: GET /api/v1/tenant/{tenant_id}/invite/active

    """
    invitation = await tenant_invite_svc.get_active_code(tenant_id)
    if not invitation:
        return None
    return ResponseInvitationWithCodeDTO(
        code=invitation.code,
        expires_at=invitation.expires_at,
    )
