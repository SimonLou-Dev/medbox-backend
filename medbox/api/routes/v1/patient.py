"""Router for patient management."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Security, status

from medbox.core.dto.patient import PatientListResponse, PatientRequest, PatientResponse
from medbox.core.services import (
    CurrentUser,
    TenantRightSvcDep,
    oauth2_scheme,
)
from medbox.core.services.patient import PatientService

router = APIRouter(prefix="/patients", tags=["Patients"])

# ==============================================================================
# Dependencies
# ==============================================================================


def get_patient_service(
    user: CurrentUser,
    tenant_right_svc: TenantRightSvcDep,
) -> PatientService:
    """Create a patient service instance."""
    return PatientService(
        tenant_id=user.tenant_id,
        tenant_right_svc=tenant_right_svc,
    )


PatientSvcDep = Annotated[PatientService, Depends(get_patient_service)]


# ==============================================================================
# Routes
# ==============================================================================


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(oauth2_scheme)],
)
async def create_patient(
    body: PatientRequest,
    user: CurrentUser,
    patient_svc: PatientSvcDep,
) -> PatientResponse:
    """Create a new patient.

    Requires user to belong to the tenant.

    Args:
        body: Patient data to create
        user: Authenticated user
        patient_svc: Patient service

    Returns:
        Created patient with information

    """
    return await patient_svc.create(body)


@router.get("/", dependencies=[Security(oauth2_scheme)])
async def list_patients(
    user: CurrentUser,
    patient_svc: PatientSvcDep,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query()] = None,
    sort_by: Annotated[
        str,
        Query(
            description="Sort field: c_first_name, c_last_name, birth_date",
        ),
    ] = "c_last_name",
    sort_order: Annotated[
        str,
        Query(description="Sort order: asc or desc"),
    ] = "asc",
) -> PatientListResponse:
    """Get paginated list of all patients for the tenant.

    Supports search by first/last name and sorting.

    Requires user to belong to the tenant.

    Args:
        user: Authenticated user
        patient_svc: Patient service
        page: Page number (default 1)
        per_page: Items per page (default 20, max 100)
        search: Search term for first_name or last_name
        sort_by: Field to sort by (default c_last_name)
        sort_order: Sort order asc or desc (default asc)

    Returns:
        Paginated list of patients

    """
    return await patient_svc.list_paginated(
        page=page,
        per_page=per_page,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/{patient_id}", dependencies=[Security(oauth2_scheme)])
async def get_patient(
    patient_id: UUID,
    user: CurrentUser,
    patient_svc: PatientSvcDep,
) -> PatientResponse:
    """Get patient information.

    Requires user to belong to patient's tenant.

    Args:
        patient_id: Patient UUID
        user: Authenticated user
        patient_svc: Patient service

    Returns:
        Patient information

    """
    return await patient_svc.get(patient_id)


@router.patch("/{patient_id}", dependencies=[Security(oauth2_scheme)])
async def update_patient(
    patient_id: UUID,
    body: PatientRequest,
    user: CurrentUser,
    patient_svc: PatientSvcDep,
) -> PatientResponse:
    """Update a patient.

    Requires user to belong to patient's tenant.

    Args:
        patient_id: Patient UUID
        body: New patient data
        user: Authenticated user
        patient_svc: Patient service

    Returns:
        Updated patient

    """
    return await patient_svc.update(patient_id, body)


@router.delete(
    "/{patient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Security(oauth2_scheme)],
)
async def delete_patient(
    patient_id: UUID,
    user: CurrentUser,
    patient_svc: PatientSvcDep,
) -> None:
    """Delete a patient.

    Requires user to belong to patient's tenant.

    Args:
        patient_id: Patient UUID
        user: Authenticated user
        patient_svc: Patient service

    """
    await patient_svc.delete(patient_id)
