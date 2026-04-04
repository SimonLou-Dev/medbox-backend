"""Tâches Celery — planification et dispatch des prises de médicaments."""

import asyncio
import logging
from datetime import UTC, datetime

from medbox.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="medbox.schedulerworker.tasks.scheduling.dispatch_scheduled_takes",
    queue="scheduler",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def dispatch_scheduled_takes(self) -> dict:
    """Dispatch les prises de médicaments dont l'heure est dépassée.

    Récupère tous les PrescriptionScheduleItem en statut 'pending'
    dont scheduled_at <= maintenant, puis envoie une tâche IoT Worker
    pour chaque box concernée.

    Fréquence : toutes les 5 minutes via Celery Beat.
    """

    async def _run() -> dict:
        from medbox.core.db.repositories.prescription_schedule_item import (
            PrescriptionScheduleItemRepository,
        )
        from medbox.iotworker.tasks.dispense import send_dispense_command

        repo = PrescriptionScheduleItemRepository()
        due_items = await repo.list_due(now=datetime.now(tz=UTC))

        if not due_items:
            logger.debug("dispatch_scheduled_takes : aucune prise due")
            return {"dispatched": 0}

        dispatched = 0
        for item in due_items:
            if not item.box_id:
                logger.warning("Schedule item %s sans box_id, ignoré", item.id)
                continue

            # Récupérer le box_uid depuis la DB
            from medbox.core.db.repositories.box import BoxRepository

            box_repo = BoxRepository(tenant_id=item.tenant_id)
            box = await box_repo.get(item.box_id)

            if not box or box.status != "active":
                logger.warning(
                    "Box %s absente ou inactive pour item %s", item.box_id, item.id
                )
                continue

            # Envoyer la commande à l'IoT Worker via Celery
            send_dispense_command.apply_async(
                args=[box.box_uid, str(item.id), str(item.prescription_item_id)],
                queue="iot",
            )
            dispatched += 1

        logger.info("dispatch_scheduled_takes : %d prises envoyées", dispatched)
        return {"dispatched": dispatched, "total_due": len(due_items)}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("Erreur dispatch_scheduled_takes : %s", exc)
        raise self.retry(exc=exc) from exc


@celery_app.task(
    name="medbox.schedulerworker.tasks.scheduling.calculate_prescription_scheduling",
    queue="scheduler",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def calculate_prescription_scheduling(self) -> dict:
    """Calcule et crée les PrescriptionScheduleItem pour les prochaines 24h.

    Pour chaque prescription active, génère les items de planning
    en fonction de la fréquence définie (frequency.times_per_day).

    Fréquence : toutes les heures via Celery Beat.
    """

    async def _run() -> dict:
        from sqlalchemy import select

        from medbox.core.db.models.prescription import Prescription
        from medbox.core.db.models.prescription_schedule_item import (
            PrescriptionScheduleItem,
        )
        from medbox.core.db.repositories.prescription_schedule_item import (
            PrescriptionScheduleItemRepository,
        )
        from medbox.core.db.session import async_session_local

        created = 0

        async with async_session_local() as session:
            # Prescriptions actives avec leurs items
            from sqlalchemy.orm import selectinload

            stmt = (
                select(Prescription)
                .where(Prescription.status == "active")
                .options(selectinload(Prescription.items))
            )
            result = await session.execute(stmt)
            prescriptions = result.scalars().all()

        repo = PrescriptionScheduleItemRepository()
        now = datetime.now(tz=UTC)

        for prescription in prescriptions:
            for item in prescription.items:
                frequency = item.frequency or {}
                times_per_day = frequency.get("times_per_day", 1) or 1

                # Calcule les horaires de la prochaine journée
                from datetime import timedelta

                interval_hours = 24 // times_per_day

                for i in range(times_per_day):
                    # Prochaine prise (à partir de maintenant + intervalle)
                    scheduled_at = now + timedelta(hours=interval_hours * (i + 1))

                    # Idempotence : vérifier si un item similaire existe déjà
                    existing = await repo.list_by_prescription(prescription.id)
                    already_exists = any(
                        abs((e.scheduled_at - scheduled_at).total_seconds()) < 300
                        and e.prescription_item_id == item.id
                        and e.status == "pending"
                        for e in existing
                        if True
                    )

                    if already_exists:
                        continue

                    schedule_item = PrescriptionScheduleItem(
                        tenant_id=prescription.tenant_id,
                        prescription_id=prescription.id,
                        prescription_item_id=item.id,
                        scheduled_at=scheduled_at,
                        status="pending",
                    )
                    await repo.create(schedule_item)
                    created += 1

        logger.info(
            "calculate_prescription_scheduling : %d items créés pour %d prescriptions",
            created,
            len(prescriptions),
        )
        return {"created": created, "prescriptions_processed": len(prescriptions)}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("Erreur calculate_prescription_scheduling : %s", exc)
        raise self.retry(exc=exc) from exc
