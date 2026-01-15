"""Business logic service for Global Medications.

Handles medication lookups and searches for prescription workflows.
"""

from __future__ import annotations

from medbox.core.db.repositories.global_medication import GlobalMedicationRepository
from medbox.core.dto.global_medication import (
    GlobalMedicationListResponse,
    GlobalMedicationResponse,
)
from medbox.core.exceptions.not_found import ModelNotFoundError


class GlobalMedicationService:
    """Service for global medication operations.

    Provides business logic for:
    - Getting medications by CIS code
    - Searching medications by name or manufacturer
    - Listing medications with pagination
    """

    def __init__(self, repo: GlobalMedicationRepository):
        """Initialize service with repository.

        Args:
            repo: GlobalMedicationRepository for database access

        """
        self.repo = repo

    async def get_by_cis(self, cis: int) -> GlobalMedicationResponse:
        """Get medication by CIS code.

        Args:
            cis: CIS Code (Code Identifiant de Spécialité)

        Returns:
            GlobalMedicationResponse with medication details

        Raises:
            ModelNotFoundError: If medication not found

        """
        medication = await self.repo.get_by_cis(cis)
        if not medication:
            raise ModelNotFoundError("GlobalMedication", str(cis))
        return GlobalMedicationResponse.from_orm(medication)

    async def search(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
    ) -> GlobalMedicationListResponse:
        """Search medications by name or manufacturer.

        Args:
            query: Search query string
            limit: Maximum results to return (1-100)
            offset: Number of results to skip

        Returns:
            GlobalMedicationListResponse with matching medications

        """
        medications, total = await self.repo.search(query, limit, offset)

        return GlobalMedicationListResponse(
            medications=[GlobalMedicationResponse.from_orm(med) for med in medications],
            total=total,
        )

    async def list_medications(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> GlobalMedicationListResponse:
        """List all medications with pagination.

        Args:
            limit: Maximum results to return (1-500)
            offset: Number of results to skip

        Returns:
            GlobalMedicationListResponse with paginated medications

        """
        medications, total = await self.repo.list_all(limit, offset)

        return GlobalMedicationListResponse(
            medications=[GlobalMedicationResponse.from_orm(med) for med in medications],
            total=total,
        )

    async def get_total_count(self) -> int:
        """Get total count of medications in database.

        Returns:
            Total number of medications

        """
        return await self.repo.count_total()
