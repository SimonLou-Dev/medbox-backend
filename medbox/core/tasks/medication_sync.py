"""Dramatiq tasks for synchronizing medications from French BDPM API."""

import asyncio
import logging
from datetime import datetime

import dramatiq
import httpx

from medbox.core.db.models.global_medication import GlobalMedication
from medbox.core.db.repositories.global_medication import GlobalMedicationRepository
from medbox.schedulerworker import broker  # noqa: F401

logger = logging.getLogger(__name__)

# External API configuration
EXTERNAL_API_BASE_URL = "https://medicaments-api.giygas.dev"
API_TIMEOUT = 120.0  # 60 seconds for large database download


@dramatiq.actor(max_retries=2)
def sync_medications_from_api() -> dict:
    """Sync all medications from French BDPM API database.

    Dramatiq task that fetches the complete database from the external API
    and updates the local global_medications table.

    Returns:
        dict: Sync result with counts (total, inserted, errors)

    """
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
            inserted, updated, errors = loop.run_until_complete(
                _save_medications(medications_data),
            )
        finally:
            loop.close()

        logger.info(
            f"✅ Medication sync completed: "
            f"{inserted} new, {updated} updated, {errors} errors (total: {total_count})",
        )

        result = {
            "status": "success",
            "total": total_count,
            "inserted": inserted,
            "updated": updated,
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


async def _save_medications(medications_data: list) -> tuple[int, int, int]:
    """Save medications to database.
    
    Returns tuple of (inserted_count, updated_count, errors_count)
    """
    repo = GlobalMedicationRepository()
    inserted = 0
    updated = 0
    errors = 0

    for med_data in medications_data:
        try:
            cis = med_data.get("cis")
            
            # Check if medication already exists
            existing = await repo.get_by_cis(cis)
            is_new = existing is None
            
            # Parse dateAMM from DD/MM/YYYY format
            date_amm = None
            if med_data.get("dateAMM"):
                try:
                    date_amm = datetime.strptime(
                        med_data.get("dateAMM"),
                        "%d/%m/%Y",
                    ).date()
                except (ValueError, TypeError):
                    pass

            medication = GlobalMedication(
                cis=cis,
                element_pharmaceutique=med_data.get(
                    "elementPharmaceutique",
                ),
                forme_pharmaceutique=med_data.get("formePharmaceutique"),
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

    return inserted, updated, errors
