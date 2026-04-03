"""Tâches Celery de l'IoT Worker — commandes envoyées vers les boxes physiques.

Ces tâches sont produites par l'API ou le Scheduler Worker et consommées
exclusivement par ce worker (queue 'iot').
"""

import asyncio
import logging

from medbox.core.celery_app import celery_app

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Commandes vers les boxes (API → IoT Worker → MQTT)
# ---------------------------------------------------------------------------


@celery_app.task(
    name="medbox.iotworker.tasks.dispense.send_dispense_command",
    queue="iot",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def send_dispense_command(
    self,
    box_uid: str,
    schedule_item_id: str,
    prescription_item_id: str | None = None,
) -> dict:
    """Envoie une commande de distribution à une box via MQTT.

    Publié sur le topic : medbox/box/{box_uid}/cmd/dispense
    QoS 2 (exactly-once delivery).

    Args:
        box_uid: Identifiant physique de la box (ex: 'BOX-001A')
        schedule_item_id: UUID du PrescriptionScheduleItem à marquer 'dispatched'
        prescription_item_id: UUID du médicament spécifique (optionnel)
    """
    async def _run() -> dict:
        from datetime import UTC, datetime

        from medbox.core.db.repositories.prescription_schedule_item import (
            PrescriptionScheduleItemRepository,
        )

        repo = PrescriptionScheduleItemRepository()
        item = await repo.update_status(
            schedule_item_id,
            "dispatched",
            dispatched_at=datetime.now(tz=UTC),
        )

        if not item:
            logger.warning(
                "Schedule item %s introuvable pour la box %s",
                schedule_item_id,
                box_uid,
            )
            return {"status": "skipped", "reason": "item_not_found"}

        # Publier la commande sur MQTT
        import json
        import ssl

        import aiomqtt

        from medbox.core.config.settings import settings

        topic = f"medbox/box/{box_uid}/cmd/dispense"
        msg = json.dumps({
            "schedule_item_id": schedule_item_id,
            "prescription_item_id": prescription_item_id,
        })

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
            await mqtt.publish(topic, payload=msg, qos=2)

        logger.info("Commande dispense envoyée → box=%s item=%s", box_uid, schedule_item_id)
        return {"status": "dispatched", "box_uid": box_uid, "item_id": schedule_item_id}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error(
            "Erreur lors du dispatch vers la box %s : %s", box_uid, exc
        )
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Réception événements MQTT → DB (IoT Worker consomme aussi ces tâches
# lorsque le listener MQTT publie vers Celery)
# ---------------------------------------------------------------------------


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
) -> dict:
    """Traite un événement de prise confirmée reçu depuis la box via MQTT.

    Met à jour le PrescriptionScheduleItem → 'taken' et crée un Event d'audit.

    Args:
        box_uid: UID de la box ayant confirmé la prise
        schedule_item_id: UUID du PrescriptionScheduleItem concerné
        taken_at_iso: Horodatage ISO 8601 de la prise (ex: '2026-04-03T10:00:00Z')
    """
    async def _run() -> dict:
        from datetime import UTC, datetime

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
            logger.warning(
                "handle_take_event : schedule item %s introuvable", schedule_item_id
            )
            return {"status": "skipped", "reason": "item_not_found"}

        logger.info(
            "Prise confirmée : box=%s item=%s taken_at=%s",
            box_uid, schedule_item_id, taken_at_iso,
        )
        return {"status": "taken", "item_id": schedule_item_id}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("Erreur handle_take_event : %s", exc)
        raise self.retry(exc=exc)


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
    """Traite un événement d'erreur reçu depuis la box via MQTT.

    Met à jour le PrescriptionScheduleItem → 'error' et
    passe la box en statut 'maintenance'.

    Args:
        box_uid: UID de la box en erreur
        schedule_item_id: UUID du schedule item concerné (optionnel)
        error_code: Code d'erreur (ex: 'WHEEL_STUCK', 'TIMEOUT', 'DOOR_OPEN')
        tenant_id: UUID du tenant propriétaire de la box
    """
    async def _run() -> dict:
        from medbox.core.db.repositories.box import BoxRepository
        from medbox.core.db.repositories.prescription_schedule_item import (
            PrescriptionScheduleItemRepository,
        )

        results: dict = {"box_uid": box_uid, "error_code": error_code}

        # Marquer le schedule item en erreur si fourni
        if schedule_item_id:
            repo = PrescriptionScheduleItemRepository()
            await repo.update_status(
                schedule_item_id,
                "error",
                error_reason=error_code,
            )
            results["item_id"] = schedule_item_id

        # Passer la box en maintenance
        box_repo = BoxRepository(tenant_id=tenant_id)
        box = await box_repo.get_by_uid(box_uid)
        if box:
            box.status = "maintenance"
            await box_repo.update(box)
            results["box_status"] = "maintenance"
            logger.warning(
                "Box %s passée en maintenance suite à erreur %s",
                box_uid, error_code,
            )

        return results

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("Erreur handle_error_event box=%s : %s", box_uid, exc)
        raise self.retry(exc=exc)
