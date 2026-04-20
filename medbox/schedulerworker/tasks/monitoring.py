"""Tâches Celery — surveillance des boxes et alertes."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from medbox.core.celery_app import celery_app
from medbox.core.config.settings import settings

logger = logging.getLogger(__name__)


@celery_app.task(
    name="medbox.schedulerworker.tasks.monitoring.monitor_boxes",
    queue="scheduler",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def monitor_boxes(self) -> dict:
    """Surveille l'etat des boxes et enregistre un event 'box_offline' si besoin.

    Detecte les boxes dont last_seen_at depasse BOX_OFFLINE_THRESHOLD_MINUTES
    (meme seuil que get_stats() — source unique).

    Frequence : toutes les 5 minutes via Celery Beat.

    Note : la connection_status est calculee dynamiquement cote DTO, donc pas
    besoin de muter Box.status (qui reste reserve au statut administratif).
    On se contente d'enregistrer un event pour l'alerte / la feed d'activite.
    """

    async def _run() -> dict:
        from sqlalchemy import select

        from medbox.core.db.models.box import Box
        from medbox.core.db.models.event import Event
        from medbox.core.db.session import async_session_local

        now = datetime.now(tz=UTC)
        threshold_minutes = settings.box_offline_threshold_minutes
        offline_cutoff = now - timedelta(minutes=threshold_minutes)
        # Un event 'box_offline' n'est emis qu'une fois par fenetre pour eviter
        # le spam : on ne re-emet pas si un event identique existe deja apres
        # la derniere telemetry.
        alerts: list[dict] = []

        async with async_session_local() as session:
            result = await session.execute(
                select(Box).where(Box.status == "active")
            )
            boxes = result.scalars().all()

            for box in boxes:
                if box.last_seen_at is None:
                    continue
                # Ne pas emettre d'event pour une box non rattachee a un tenant
                if box.tenant_id is None:
                    continue
                last_seen = box.last_seen_at
                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=UTC)
                if last_seen >= offline_cutoff:
                    continue

                # Box offline : verifier qu'on n'a pas deja emis un event
                # 'box_offline' depuis la derniere telemetry
                existing = await session.execute(
                    select(Event)
                    .where(Event.box_id == box.id)
                    .where(Event.type == "box_offline")
                    .where(Event.created_at > last_seen)
                    .limit(1)
                )
                if existing.scalar_one_or_none() is not None:
                    continue

                event = Event(
                    tenant_id=box.tenant_id,
                    box_id=box.id,
                    type="box_offline",
                    payload={
                        "box_uid": box.box_uid,
                        "last_seen_at": last_seen.isoformat(),
                        "threshold_minutes": threshold_minutes,
                    },
                )
                session.add(event)
                alerts.append(
                    {
                        "type": "box_offline",
                        "box_uid": box.box_uid,
                        "box_id": str(box.id),
                        "last_seen_at": last_seen.isoformat(),
                    }
                )
                logger.warning(
                    "Box %s offline depuis %s (seuil %dmin)",
                    box.box_uid,
                    last_seen,
                    threshold_minutes,
                )

            if alerts:
                await session.commit()

        logger.info(
            "monitor_boxes : %d boxes verifiees, %d alertes",
            len(boxes),
            len(alerts),
        )
        return {
            "boxes_checked": len(boxes),
            "alerts": len(alerts),
            "alert_details": alerts,
        }

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("Erreur monitor_boxes : %s", exc)
        raise self.retry(exc=exc) from exc
