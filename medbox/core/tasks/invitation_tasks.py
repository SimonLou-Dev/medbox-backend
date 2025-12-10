import dramatiq


@dramatiq.actor(queue_name="tenant_invitation")
async def expire_invitation(invite_id: str) -> None:
    """Marque une invitation comme expirée."""
    from medbox.core.services import (
        TenantInvitationService,
        get_tenant_invitation_service,
    )

    svc: TenantInvitationService = get_tenant_invitation_service()

    await svc.expire_invitation(invite_id)
