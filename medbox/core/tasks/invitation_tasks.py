"""Tâches Celery liées aux invitations."""

import asyncio
import logging

from medbox.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="medbox.core.tasks.invitation_tasks.expire_invitation",
    queue="default",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def expire_invitation(self, invite_id: str) -> None:
    """Marque une invitation comme expirée.

    Envoyée par l'API 10 minutes après la création d'un code
    pour garantir l'expiration même si le scheduler est indisponible.
    """
    from medbox.core.db.repositories.invitation import InvitationRepository
    from medbox.core.exceptions import ModelNotFoundError
    from medbox.core.services.tenant_invitation import TenantInvitationService

    async def _run() -> None:
        svc = TenantInvitationService(
            user_repo=None,
            tenant_repo=None,
            invite_repo=InvitationRepository(),
        )
        try:
            await svc.expire_invitation(invite_id)
            logger.info("Invitation %s expirée avec succès", invite_id)
        except ModelNotFoundError:
            logger.warning(
                "Invitation %s introuvable, déjà expirée ou supprimée", invite_id
            )

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error(
            "Erreur lors de l'expiration de l'invitation %s : %s", invite_id, exc
        )
        raise self.retry(exc=exc)
