"""API routes for Global Medications (French BDPM reference data).

Provides endpoints for searching and retrieving medications
used in prescription workflows.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from medbox.core.db.repositories.global_medication import GlobalMedicationRepository
from medbox.core.dto.global_medication import (
    GlobalMedicationListResponse,
    GlobalMedicationResponse,
)
from medbox.core.exceptions.not_found import ModelNotFoundError
from medbox.core.services.global_medication import GlobalMedicationService

# Create router for global medication endpoints
global_medication_router = APIRouter(
    prefix="/global-medications",
    tags=["Global Medications"],
)


# Dependency injection for GlobalMedicationService
def get_global_medication_service() -> GlobalMedicationService:
    """Get GlobalMedicationService with injected dependencies.

    Returns
    -------
    GlobalMedicationService
        Service instance

    """
    repo = GlobalMedicationRepository()
    return GlobalMedicationService(repo)


@global_medication_router.get(
    "/search",
    response_model=GlobalMedicationListResponse,
    summary="Search medications",
    description="Search medications by name or manufacturer (case-insensitive)",
)
async def search_medications(
    query: str = Query(
        ...,
        min_length=1,
        max_length=255,
        description="Search query for medication name or manufacturer",
        examples=["paracetamol", "mylan"],
    ),
    limit: int = Query(
        20,
        ge=1,
        le=100,
        description="Maximum results to return",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of results to skip",
    ),
    service: GlobalMedicationService = Depends(get_global_medication_service),
) -> GlobalMedicationListResponse:
    """Search medications by name or manufacturer.

    Searches both:
    - **element_pharmaceutique**: Product name
    - **titulaire**: Manufacturer/license holder

    Returns:
        List of matching medications with total count

    """
    return await service.search(query, limit, offset)


@global_medication_router.get(
    "",
    response_model=GlobalMedicationListResponse,
    summary="List all medications",
    description="Get paginated list of all medications in the BDPM database",
)
async def list_medications(
    limit: int = Query(
        100,
        ge=1,
        le=500,
        description="Maximum results to return",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of results to skip",
    ),
    service: GlobalMedicationService = Depends(get_global_medication_service),
) -> GlobalMedicationListResponse:
    """Get paginated list of all medications.

    Returns:
        Paginated list of medications with total count

    """
    return await service.list_medications(limit, offset)


@global_medication_router.get(
    "/{cis}",
    response_model=GlobalMedicationResponse,
    summary="Get medication by CIS code",
    description="Get detailed information about a medication using its CIS code",
)
async def get_medication_by_cis(
    cis: int = Path(
        ...,
        gt=0,
        lt=1000000000,
        description="CIS Code (Code Identifiant de Spécialité)",
        examples=[61504672, 60001234],
    ),
    service: GlobalMedicationService = Depends(get_global_medication_service),
) -> GlobalMedicationResponse:
    """Get medication details by CIS code.

    Args:
        cis: CIS Code (1 - 999999999)

    Returns:
        Detailed medication information

    Raises:
        HTTPException 404: If medication not found

    """
    try:
        return await service.get_by_cis(cis)
    except ModelNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
