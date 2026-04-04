"""Tâches Celery — surveillance des boxes et alertes."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from medbox.core.celery_app import celery_app

logger = logging.getLogger(__name__)

OFFLINE_THRESHOLD_MINUTES = 15


@celery_app.task(
    name="medbox.schedulerworker.tasks.monitoring.monitor_boxes",
    queue="scheduler",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def monitor_boxes(self) -> dict:
    """Surveille l'état des boxes et génère des alertes si nécessaire.

    Détecte les boxes offline (last_seen_at > 15 minutes).
    Fréquence : toutes les 5 minutes via Celery Beat.
    """
    async def _run() -> dict:
        from sqlalchemy import select

        from medbox.core.db.models.box import Box
        from medbox.core.db.session import async_session_local

        now = datetime.now(tz=UTC)
        offline_cutoff = now - timedelta(minutes=OFFLINE_THRESHOLD_MINUTES)
        alerts: list[dict] = []

        async with async_session_local() as session:
            result = await session.execute(select(Box).where(Box.status == "active"))
            boxes = result.scalars().all()

        for box in boxes:
            if box.last_seen_at is None:
                continue
            last_seen = box.last_seen_at
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=UTC)
            if last_seen < offline_cutoff:
                alerts.append({
                    "type": "box_offline",
                    "box_uid": box.box_uid,
                    "box_id": str(box.id),
                    "last_seen_at": box.last_seen_at.isoformat(),
                })
                logger.warning("Box %s offline depuis %s", box.box_uid, box.last_seen_at)

        logger.info("monitor_boxes : %d boxes vérifiées, %d alertes", len(boxes), len(alerts))
        return {"boxes_checked": len(boxes), "alerts": len(alerts), "alert_details": alerts}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("Erreur monitor_boxes : %s", exc)
        raise self.retry(exc=exc)
