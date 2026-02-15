"""Router pour le panneau d'administration du tenant."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from medbox.core.constants.enums import UserRoles
from medbox.core.dto.admin import (
    ActivityFeedResponse,
    InvitationHistoryResponse,
    MemberListResponse,
    MemberResponse,
    TenantStatsResponse,
    UpdateMemberRoleRequest,
)
from medbox.core.services import (
    AdminSvcDep,
    UserContext,
    UserSvcDep,
)
from medbox.core.services.tenant_right import require_tenant_role

router = APIRouter(
    prefix="/tenant/{tenant_id}/admin",
    tags=["Admin"],
)


@router.get("/stats")
async def get_tenant_stats(
    tenant_id: UUID,
    _: Annotated[UserContext, Depends(require_tenant_role(UserRoles.TENANT_ADMIN))],
    admin_svc: AdminSvcDep,
) -> TenantStatsResponse:
    """Stats agregees du tenant. Necessite TENANT_ADMIN."""
    return await admin_svc.get_stats(tenant_id)


@router.get("/members")
async def list_members(
    tenant_id: UUID,
    _: Annotated[UserContext, Depends(require_tenant_role(UserRoles.TENANT_ADMIN))],
    admin_svc: AdminSvcDep,
) -> MemberListResponse:
    """List des membres du tenant. Necessite TENANT_ADMIN."""
    return await admin_svc.list_members(tenant_id)


@router.patch("/members/{member_id}/role")
async def update_member_role(
    tenant_id: UUID,
    member_id: UUID,
    body: UpdateMemberRoleRequest,
    user_ctx: Annotated[
        UserContext,
        Depends(require_tenant_role(UserRoles.TENANT_ADMIN)),
    ],
    admin_svc: AdminSvcDep,
    user_svc: UserSvcDep,
) -> MemberResponse:
    """Change le role d'un membre. Necessite TENANT_ADMIN."""
    admin_user = await user_svc.get_user_from_subject(user_ctx.subject)
    return await admin_svc.update_member_role(
        tenant_id=tenant_id,
        member_id=member_id,
        new_role=body.role,
        admin_user_id=admin_user.id,
    )


@router.delete(
    "/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    tenant_id: UUID,
    member_id: UUID,
    user_ctx: Annotated[
        UserContext,
        Depends(require_tenant_role(UserRoles.TENANT_ADMIN)),
    ],
    admin_svc: AdminSvcDep,
    user_svc: UserSvcDep,
) -> None:
    """Retire un membre du tenant. Necessite TENANT_ADMIN."""
    admin_user = await user_svc.get_user_from_subject(user_ctx.subject)
    await admin_svc.remove_member(
        tenant_id=tenant_id,
        member_id=member_id,
        admin_user_id=admin_user.id,
    )


@router.get("/invitations")
async def get_invitation_history(
    tenant_id: UUID,
    _: Annotated[UserContext, Depends(require_tenant_role(UserRoles.TENANT_ADMIN))],
    admin_svc: AdminSvcDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> InvitationHistoryResponse:
    """Historique des invitations du tenant. Necessite TENANT_ADMIN."""
    return await admin_svc.get_invitation_history(tenant_id, limit=limit, offset=offset)


@router.get("/activity")
async def get_activity_feed(
    tenant_id: UUID,
    _: Annotated[UserContext, Depends(require_tenant_role(UserRoles.TENANT_ADMIN))],
    admin_svc: AdminSvcDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> ActivityFeedResponse:
    """Fil d'activite du tenant. Necessite TENANT_ADMIN."""
    return await admin_svc.get_activity_feed(tenant_id, limit=limit)
