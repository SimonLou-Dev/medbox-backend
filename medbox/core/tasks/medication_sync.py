"""Tâche Celery de synchronisation des médicaments depuis l'API BDPM française."""

import asyncio
import logging
from datetime import datetime

import httpx

from medbox.core.celery_app import celery_app
from medbox.core.db.models.global_medication import GlobalMedication
from medbox.core.db.repositories.global_medication import GlobalMedicationRepository
from medbox.core.filters import is_medbox_1_compatible
from medbox.core.utils.redis_lock import get_task_lock

logger = logging.getLogger(__name__)

# External API configuration
EXTERNAL_API_BASE_URL = "https://medicaments-api.giygas.dev"
API_TIMEOUT = 120.0  # 60 seconds for large database download


@celery_app.task(
    name="medbox.core.tasks.medication_sync.sync_medications_from_api",
    queue="default",
    max_retries=2,
)
def sync_medications_from_api() -> dict:
    """Synchronise les médicaments depuis l'API BDPM française.

    Tâche Celery planifiée quotidiennement à 03:00 UTC via Celery Beat.
    Utilise un verrou Redis pour éviter les exécutions concurrentes.

    Returns:
        dict: Résultat avec compteurs (total, inserted, updated, errors)

    """
    # Acquire distributed lock with 1-hour rate limit
    lock = get_task_lock("sync_medications_from_api", max_age_minutes=60)

    try:
        if not lock.acquire():
            logger.info(
                "⏭️  Medication sync already running or rate-limited. "
                "Max once per hour.",
            )
            return {
                "status": "skipped",
                "reason": "Rate limited - max once per hour",
                "timestamp": datetime.utcnow().isoformat(),
            }
    except RuntimeError as e:
        logger.warning(f"⏭️  {e}")
        return {
            "status": "skipped",
            "reason": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }

    logger.info("🔄 Starting medication sync from French BDPM API...")

    try:
        # Fetch the complete database from API
        logger.info("📥 Downloading medications database from API...")

        # Run async code in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            api_data = loop.run_until_complete(_fetch_api_data())
        finally:
            loop.close()

        medications_data = api_data

        # Handle both list and dict responses from API
        if isinstance(api_data, dict):
            medications_data = api_data.get("results", [])
        elif not isinstance(api_data, list):
            medications_data = []

        total_count = len(medications_data)
        logger.info(f"📊 Downloaded {total_count} medications from API")

        # Save to database
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            inserted, updated, filtered, errors = loop.run_until_complete(
                _save_medications(medications_data),
            )
        finally:
            loop.close()

        logger.info(
            f"✅ Medication sync completed: "
            f"{inserted} new, {updated} updated, {filtered} filtered, {errors} errors "
            f"(total: {total_count})",
        )

        result = {
            "status": "success",
            "total": total_count,
            "inserted": inserted,
            "updated": updated,
            "filtered": filtered,
            "errors": errors,
            "timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(f"📈 Sync result: {result}")
        return result

    except Exception as e:
        logger.error(f"❌ Unexpected error during medication sync: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }
    finally:
        # Release the lock when done
        lock.release()
        logger.info("🔓 Released medication sync lock")


async def _fetch_api_data() -> dict | list:
    """Fetch data from external API."""
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.get(
                f"{EXTERNAL_API_BASE_URL}/database",
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ API error during sync: {e}")
        raise


async def _save_medications(medications_data: list) -> tuple[int, int, int, int]:
    """Save medications to database.

    Filters medications to only save those compatible with MedBox 1 (5cm x 5cm x 5cm).

    Returns tuple of (inserted_count, updated_count, filtered_count, errors_count)
    """
    repo = GlobalMedicationRepository()
    inserted = 0
    updated = 0
    filtered = 0
    errors = 0

    for med_data in medications_data:
        try:
            cis = med_data.get("cis")
            form = med_data.get("formePharmaceutique", "")

            # Check if medication form is compatible with MedBox 1
            if not is_medbox_1_compatible(form):
                logger.debug(
                    f"Filtered out medication CIS {cis}: form '{form}' not compatible",
                )
                filtered += 1
                continue

            # Check if medication already exists
            existing = await repo.get_by_cis(cis)
            is_new = existing is None

            # Parse dateAMM from DD/MM/YYYY format
            date_amm = None
            if med_data.get("dateAMM"):
                date_amm = datetime.strptime(
                    med_data.get("dateAMM"),
                    "%d/%m/%Y",
                ).date()

            medication = GlobalMedication(
                cis=cis,
                element_pharmaceutique=med_data.get(
                    "elementPharmaceutique",
                ),
                forme_pharmaceutique=form,
                voies_administration=med_data.get("voiesAdministration"),
                status_autorisation=med_data.get("statusAutorisation"),
                type_procedure=med_data.get("typeProcedure"),
                etat_commercialisation=med_data.get(
                    "etatComercialisation",
                ),
                date_amm=date_amm,
                titulaire=med_data.get("titulaire"),
            )

            # Upsert to handle concurrent access
            result = await repo.upsert_medication(medication)
            if result:
                if is_new:
                    inserted += 1
                else:
                    updated += 1

        except Exception as e:
            logger.error(f"Error saving medication CIS {med_data.get('cis')}: {e}")
            errors += 1
            continue

    return inserted, updated, filtered, errors
