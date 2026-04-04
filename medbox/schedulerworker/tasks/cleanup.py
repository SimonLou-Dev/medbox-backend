"""Tâches Celery — nettoyage quotidien de la base de données."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from medbox.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="medbox.schedulerworker.tasks.cleanup.cleanup_job",
    queue="scheduler",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def cleanup_job(self) -> dict:
    """Nettoyage quotidien de la base de données.

    - Expire les invitations PENDING expirées
    - Marque les PrescriptionScheduleItem PENDING dépassés comme 'missed'
    - Archive les events anciens (> 1 an) [TODO]

    Planifié quotidiennement à 02:00 UTC via Celery Beat.
    """

    async def _run() -> dict:
        from sqlalchemy import select

        from medbox.core.constants.enums import InviteStatus
        from medbox.core.db.models.invitation import Invitation
        from medbox.core.db.models.prescription_schedule_item import (
            PrescriptionScheduleItem,
        )
        from medbox.core.db.session import async_session_local

        now = datetime.now(tz=UTC)
        stats: dict[str, int] = {}

        async with async_session_local() as session:
            # 1. Expirer les invitations PENDING expirées
            stmt = (
                select(Invitation)
                .where(Invitation.status == InviteStatus.PENDING)
                .where(Invitation.expires_at < now)
            )
            result = await session.execute(stmt)
            expired_invitations = result.scalars().all()

            for inv in expired_invitations:
                inv.status = InviteStatus.EXPIRED

            if expired_invitations:
                await session.commit()

            stats["invitations_expired"] = len(expired_invitations)

        async with async_session_local() as session:
            # 2. Marquer les prises PENDING dépassées de > 2h comme 'missed'
            missed_cutoff = now - timedelta(hours=2)
            stmt = (
                select(PrescriptionScheduleItem)
                .where(PrescriptionScheduleItem.status == "pending")
                .where(PrescriptionScheduleItem.scheduled_at < missed_cutoff)
            )
            result = await session.execute(stmt)
            overdue_items = result.scalars().all()

            for item in overdue_items:
                item.status = "missed"

            if overdue_items:
                await session.commit()

            stats["schedule_items_missed"] = len(overdue_items)

        logger.info(
            "cleanup_job terminé : %d invitations expirées, %d prises missed",
            stats.get("invitations_expired", 0),
            stats.get("schedule_items_missed", 0),
        )
        return stats

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("Erreur cleanup_job : %s", exc)
        raise self.retry(exc=exc) from exc
