import dramatiq


@dramatiq.actor(queue_name="tenant_invitation")
async def expire_invitation(invite_id: str):
    """Marque une invitation comme expirée."""
    from medbox.core.db.repositories.invitation import InvitationRepository

    repo = InvitationRepository()

    # Charger l'invitation
    invite = await repo.get(invite_id)
    if not invite:
        return

    # Marquer comme expiré
    await repo.update(invite_id, {"status": "EXPIRED"})
