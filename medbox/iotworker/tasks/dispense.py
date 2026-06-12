"""Tâches Celery de l'IoT Worker — réception événements MQTT depuis les medboxes.

Ces tâches sont déclenchées par le listener MQTT quand une medbox confirme
une distribution ou signale une erreur.
"""

import asyncio
import logging

from medbox.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="medbox.iotworker.tasks.dispense.handle_take_event",
    queue="iot",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def handle_take_event(
    self,
    box_uid: str,
    schedule_item_id: str,
    taken_at_iso: str,
    tenant_id: str | None = None,
) -> dict:
    """Traite la confirmation de distribution reçue depuis la medbox via MQTT.

    La medbox fait tourner la roue de manière autonome à l'heure prévue
    et envoie cet événement une fois la case libérée.

    Args:
        box_uid: UID de la medbox
        schedule_item_id: UUID du PrescriptionScheduleItem concerné
        taken_at_iso: Horodatage ISO 8601 fourni par la medbox
        tenant_id: UUID du tenant (pour notif WS)
    """

    async def _run() -> dict:
        from datetime import UTC, datetime

        from medbox.api.ws.events import take_event as ws_take_event
        from medbox.api.ws.manager import publish_to_tenant
        from medbox.core.db.repositories.prescription_schedule_item import (
            PrescriptionScheduleItemRepository,
        )

        taken_at = datetime.fromisoformat(taken_at_iso).replace(tzinfo=UTC)
        repo = PrescriptionScheduleItemRepository()

        item = await repo.update_status(
            schedule_item_id,
            "taken",
            taken_at=taken_at,
        )

        if not item:
            logger.warning("handle_take_event : item %s introuvable", schedule_item_id)
            return {"status": "skipped", "reason": "item_not_found"}

        # Notifier le front via WS
        if tenant_id:
            try:
                await publish_to_tenant(
                    tenant_id,
                    ws_take_event(box_uid, schedule_item_id, "taken"),
                )
            except Exception as ws_exc:
                logger.debug("WS publish failed (non-blocking) : %s", ws_exc)

        logger.info(
            "Distribution confirmée : box=%s item=%s taken_at=%s",
            box_uid,
            schedule_item_id,
            taken_at_iso,
        )
        return {"status": "taken", "item_id": schedule_item_id}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("Erreur handle_take_event : %s", exc)
        raise self.retry(exc=exc) from exc


@celery_app.task(
    name="medbox.iotworker.tasks.dispense.handle_error_event",
    queue="iot",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def handle_error_event(
    self,
    box_uid: str,
    schedule_item_id: str | None,
    error_code: str,
    tenant_id: str,
) -> dict:
    """Traite une erreur de distribution signalée par la medbox via MQTT.

    Met à jour le PrescriptionScheduleItem → 'error', passe la box
    en statut 'maintenance' et notifie le front via WS.

    Args:
        box_uid: UID de la medbox en erreur
        schedule_item_id: UUID de la distribution concernée (optionnel)
        error_code: Code d'erreur (ex: 'WHEEL_STUCK', 'TIMEOUT', 'DOOR_OPEN')
        tenant_id: UUID du tenant propriétaire de la box
    """

    async def _run() -> dict:
        from medbox.api.ws.events import box_alert
        from medbox.api.ws.events import take_event as ws_take_event
        from medbox.api.ws.manager import publish_to_tenant
        from medbox.core.db.repositories.box import BoxRepository
        from medbox.core.db.repositories.prescription_schedule_item import (
            PrescriptionScheduleItemRepository,
        )

        results: dict = {"box_uid": box_uid, "error_code": error_code}

        if schedule_item_id:
            repo = PrescriptionScheduleItemRepository()
            await repo.update_status(
                schedule_item_id,
                "error",
                error_reason=error_code,
            )
            results["item_id"] = schedule_item_id

        box_repo = BoxRepository(tenant_id=tenant_id)
        box = await box_repo.get_by_uid(box_uid)
        if box:
            box.status = "maintenance"
            await box_repo.update(box)
            results["box_status"] = "maintenance"
            logger.warning(
                "Box %s passée en maintenance suite à erreur %s", box_uid, error_code
            )

        # Notifier le front via WS
        try:
            events = [
                box_alert(
                    box_uid,
                    "maintenance",
                    f"Box {box_uid} en maintenance : {error_code}",
                ),
            ]
            if schedule_item_id:
                events.append(ws_take_event(box_uid, schedule_item_id, "error"))
            for event in events:
                await publish_to_tenant(tenant_id, event)
        except Exception as ws_exc:
            logger.debug("WS publish failed (non-blocking) : %s", ws_exc)

        return results

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("Erreur handle_error_event box=%s : %s", box_uid, exc)
        raise self.retry(exc=exc) from exc
