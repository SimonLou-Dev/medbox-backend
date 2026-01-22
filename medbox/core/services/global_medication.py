"""Business logic service for Global Medications.

Handles medication lookups and searches for prescription workflows.
Includes fallback to external French BDPM API if not found locally.
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

from medbox.core.db.models.global_medication import GlobalMedication
from medbox.core.db.repositories.global_medication import GlobalMedicationRepository
from medbox.core.dto.global_medication import (
    GlobalMedicationListResponse,
    GlobalMedicationResponse,
)
from medbox.core.exceptions.not_found import ModelNotFoundError

logger = logging.getLogger(__name__)

# External API configuration
EXTERNAL_API_BASE_URL = "https://medicaments-api.giygas.dev"
API_TIMEOUT = 10.0


class GlobalMedicationService:
    """Service for global medication operations.

    Provides business logic for:
    - Getting medications by CIS code (with API fallback)
    - Searching medications by name or manufacturer (with API fallback)
    - Listing medications with pagination
    - Fetching from external French BDPM API if not found locally
    """

    def __init__(self, repo: GlobalMedicationRepository):
        """Initialize service with repository.

        Args:
            repo: GlobalMedicationRepository for database access

        """
        self.repo = repo

    async def _fetch_from_external_api(
        self,
        endpoint: str,
        params: dict | None = None,
    ) -> dict | None:
        """Fetch data from external French medications API.

        Args:
            endpoint: API endpoint to call (e.g., "api/medications/{cis}")
            params: Optional query parameters

        Returns:
            API response data or None if not found/error

        """
        try:
            url = f"{EXTERNAL_API_BASE_URL}/{endpoint}"
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(f"Medication not found in external API: {endpoint}")
                return None
            logger.error(f"Error fetching from external API: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching from external API: {e}")
            return None

    async def _save_to_database(self, api_data: dict) -> GlobalMedication | None:
        """Save medication fetched from API to local database.

        Uses upsert to safely handle concurrent inserts.

        Args:
            api_data: Medication data from external API

        Returns:
            Created or existing GlobalMedication or None if save failed

        """
        try:
            # Parse dateAMM from DD/MM/YYYY format
            date_amm = None
            if api_data.get("dateAMM"):
                try:
                    date_amm = datetime.strptime(
                        api_data.get("dateAMM"),
                        "%d/%m/%Y",
                    ).date()
                except (ValueError, TypeError):
                    logger.warning(
                        f"Failed to parse dateAMM: {api_data.get('dateAMM')}",
                    )

            medication = GlobalMedication(
                cis=api_data.get("cis"),
                element_pharmaceutique=api_data.get("elementPharmaceutique"),
                forme_pharmaceutique=api_data.get("formePharmaceutique"),
                voies_administration=api_data.get("voiesAdministration"),
                status_autorisation=api_data.get("statusAutorisation"),
                type_procedure=api_data.get("typeProcedure"),
                etat_commercialisation=api_data.get("etatComercialisation"),
                date_amm=date_amm,
                titulaire=api_data.get("titulaire"),
            )
            # Use upsert to handle concurrent inserts safely
            return await self.repo.upsert_medication(medication)
        except Exception as e:
            logger.error(f"Error saving medication to database: {e}")
            return None

    async def get_by_cis(self, cis: int) -> GlobalMedicationResponse:
        """Get medication by CIS code.

        First searches local database, then falls back to external API if not found.

        Args:
            cis: CIS Code (Code Identifiant de Spécialité)

        Returns:
            GlobalMedicationResponse with medication details

        Raises:
            ModelNotFoundError: If medication not found in both local DB and API

        """
        # Try local database first
        medication = await self.repo.get_by_cis(cis)
        if medication:
            return GlobalMedicationResponse.from_orm(medication)

        # Fallback to external API
        api_data = await self._fetch_from_external_api(f"api/medications/{cis}")
        if api_data:
            # Try to save to database for future use
            saved_med = await self._save_to_database(api_data)
            if saved_med:
                return GlobalMedicationResponse.from_orm(saved_med)
            # Return from API data even if save failed
            return GlobalMedicationResponse.model_validate(api_data)

        raise ModelNotFoundError("GlobalMedication", str(cis))

    async def search(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
    ) -> GlobalMedicationListResponse:
        """Search medications by name or manufacturer.

        First searches local database, then falls back to external API if few results.

        Args:
            query: Search query string
            limit: Maximum results to return (1-100)
            offset: Number of results to skip

        Returns:
            GlobalMedicationListResponse with matching medications

        """
        # Try local database first
        medications, total = await self.repo.search(query, limit, offset)

        # If we have results locally, return them
        if medications and total > 0:
            return GlobalMedicationListResponse(
                medications=[
                    GlobalMedicationResponse.from_orm(med) for med in medications
                ],
                total=total,
            )

        # Fallback to external API if no local results
        api_data = await self._fetch_from_external_api(
            f"medicament/{query}",
        )

        if api_data:
            # Try to save results to database
            for item in api_data:
                await self._save_to_database(item)

            return GlobalMedicationListResponse(
                medications=[
                    GlobalMedicationResponse.from_api(med) for med in api_data
                ],
                total=len(api_data),
            )

        return GlobalMedicationListResponse(medications=[], total=0)

    async def list_medications(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> GlobalMedicationListResponse:
        """List all medications with pagination.

        Uses local database primarily, falls back to API if needed.

        Args:
            limit: Maximum results to return (1-500)
            offset: Number of results to skip

        Returns:
            GlobalMedicationListResponse with paginated medications

        """
        medications, total = await self.repo.list_all(limit, offset)

        # If we have local results, return them
        if medications or total > 0:
            return GlobalMedicationListResponse(
                medications=[
                    GlobalMedicationResponse.from_orm(med) for med in medications
                ],
                total=total,
            )

        # Fallback to external API if database is empty
        api_data = await self._fetch_from_external_api(
            "api/medications",
            params={"limit": limit, "offset": offset},
        )

        if api_data and isinstance(api_data, dict):
            results = api_data.get("results", [])
            if results:
                return GlobalMedicationListResponse(
                    medications=[
                        GlobalMedicationResponse.model_validate(med) for med in results
                    ],
                    total=api_data.get("total", len(results)),
                )

        return GlobalMedicationListResponse(medications=[], total=0)

    async def get_total_count(self) -> int:
        """Get total count of medications in database.

        Returns count from local database. Falls back to API info if needed.

        Returns:
            Total number of medications

        """
        count = await self.repo.count_total()

        # If local database is empty, try to get count from API
        if count == 0:
            api_data = await self._fetch_from_external_api(
                "api/medications",
                params={"limit": 1},
            )
            if api_data and isinstance(api_data, dict):
                return api_data.get("total", 0)

        return count
