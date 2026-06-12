"""Tâche Celery — preload des prochaines distributions vers les medboxes.

2x par jour, envoie à chaque medbox active ses 3 prochaines distributions
avec leurs horaires, pour qu'elle puisse fonctionner en mode autonome/offline.
"""

import asyncio
import logging

from medbox.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="medbox.schedulerworker.tasks.preload.preload_upcoming_distributions",
    queue="scheduler",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def preload_upcoming_distributions(self) -> dict:
    """Envoie les 3 prochaines distributions à chaque medbox active via MQTT.

    Fréquence : 2x/jour (08:00 et 20:00 UTC) via Celery Beat.
    Format MQTT : medbox/box/{box_uid}/cmd/preload
    Payload : liste ordonnée des 3 prochains items avec scheduled_at et slot_index.
    """

    async def _run() -> dict:
        import json
        import ssl

        import aiomqtt
        from sqlalchemy import select

        from medbox.core.config.settings import settings
        from medbox.core.db.models.box import Box
        from medbox.core.db.models.wheel_slot_prescription_item import (
            WheelSlotPrescriptionItem,
        )
        from medbox.core.db.repositories.prescription_schedule_item import (
            PrescriptionScheduleItemRepository,
        )
        from medbox.core.db.session import async_session_local

        stats = {"boxes_processed": 0, "boxes_skipped": 0, "total_items_sent": 0}

        # Récupérer toutes les boxes actives avec leurs medbox UID
        async with async_session_local() as session:
            result = await session.execute(select(Box).where(Box.status == "active"))
            active_boxes = result.scalars().all()

        if not active_boxes:
            logger.debug("preload : aucune box active")
            return stats

        tls_ctx = ssl.create_default_context(
            ssl.Purpose.SERVER_AUTH,
            cafile=settings.emqx_ca_cert,
        )
        tls_ctx.load_cert_chain(
            certfile=settings.emqx_client_cert,
            keyfile=settings.emqx_client_key,
        )

        async with aiomqtt.Client(
            hostname=settings.emqx_host,
            port=settings.emqx_port,
            tls_context=tls_ctx,
        ) as mqtt:
            for box in active_boxes:
                try:
                    repo = PrescriptionScheduleItemRepository()
                    upcoming = await repo.list_upcoming_by_box(box.id, limit=3)

                    if not upcoming:
                        logger.debug(
                            "preload : box %s sans distribution à venir", box.box_uid
                        )
                        stats["boxes_skipped"] += 1
                        continue

                    # Construire le payload : slot_index + scheduled_at + médicaments
                    distributions = []
                    async with async_session_local() as session:
                        for item in upcoming:
                            medications = []
                            if item.wheel_slot_id:
                                links_result = await session.execute(
                                    select(WheelSlotPrescriptionItem).where(
                                        WheelSlotPrescriptionItem.wheel_slot_id
                                        == item.wheel_slot_id
                                    )
                                )
                                for link in links_result.scalars().all():
                                    medications.append(
                                        {
                                            "prescription_item_id": str(
                                                link.prescription_item_id
                                            ),
                                            "quantity": link.quantity,
                                        }
                                    )

                            distributions.append(
                                {
                                    "schedule_item_id": str(item.id),
                                    "slot_index": item.wheel_slot.index
                                    if item.wheel_slot
                                    else None,
                                    "scheduled_at": item.scheduled_at.isoformat(),
                                    "medications": medications,
                                }
                            )

                    payload = json.dumps({"distributions": distributions})
                    topic = f"medbox/box/{box.box_uid}/cmd/preload"

                    await mqtt.publish(topic, payload=payload, qos=1)

                    logger.info(
                        "preload : %d distributions envoyées → box=%s",
                        len(distributions),
                        box.box_uid,
                    )
                    stats["boxes_processed"] += 1
                    stats["total_items_sent"] += len(distributions)

                except Exception as box_exc:
                    logger.warning(
                        "preload : erreur pour box %s : %s", box.box_uid, box_exc
                    )
                    stats["boxes_skipped"] += 1

        return stats

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("Erreur preload_upcoming_distributions : %s", exc)
        raise self.retry(exc=exc) from exc
