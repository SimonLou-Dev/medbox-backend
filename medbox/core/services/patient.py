"""Service for patient management."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException, status

from medbox.core.db.models.patient import Patient
from medbox.core.db.repositories.base import Page
from medbox.core.db.repositories.patient import PatientRepository
from medbox.core.dto.pagination import PagedResponse, PaginationMeta
from medbox.core.dto.patient import PatientRequest, PatientResponse

if TYPE_CHECKING:
    from medbox.core.services.tenant_right import TenantRightService


class PatientService:
    """Service for patient management."""

    def __init__(
        self,
        tenant_id: UUID,
        tenant_right_svc: TenantRightService | None = None,
        patient_repo: PatientRepository | None = None,
    ) -> None:
        """Initialize the service.

        Parameters
        ----------
        tenant_id : UUID
            Tenant ID to enforce multi-tenant isolation
        tenant_right_svc : TenantRightService | None
            Tenant rights service (optional)
        patient_repo : PatientRepository | None
            Patient repository

        """
        self.tenant_id = tenant_id
        self.tenant_right_svc = tenant_right_svc
        self.patient_repo = patient_repo or PatientRepository(tenant_id=tenant_id)

    async def list(self) -> list[Patient]:
        """List all patients for the tenant.

        Returns
        -------
        list[Patient]
            List of patients for the tenant.

        """
        return await self.patient_repo.list()

    async def list_paginated(
        self,
        page: int = 1,
        per_page: int = 20,
        search: str | None = None,
        sort_by: str = "c_last_name",
        sort_order: str = "asc",
    ) -> PagedResponse[PatientResponse]:
        """List paginated patients for the tenant with search and sorting.

        Parameters
        ----------
        page : int
            Page number (default 1)
        per_page : int
            Number of items per page (default 20)
        search : str | None
            Search term for first_name or last_name
        sort_by : str
            Field to sort by: c_first_name, c_last_name, birth_date (default c_last_name)
        sort_order : str
            Sort order: asc or desc (default asc)

        Returns
        -------
        PagedResponse[PatientResponse]
            Paginated response with metadata

        """
        # Fetch page from repository with search and sorting
        # Note: Repository is already scoped by tenant_id
        paged_patients: Page[Patient] = await self.patient_repo.paginate(
            filters={},
            page=page,
            per_page=per_page,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        # Convert to DTOs
        items = [PatientResponse.from_model(p) for p in paged_patients.items]

        # Create pagination metadata
        pagination = PaginationMeta(
            page=paged_patients.page,
            per_page=paged_patients.per_page,
            total=paged_patients.total,
            total_pages=paged_patients.total_pages,
            has_next=paged_patients.page < paged_patients.total_pages,
            has_previous=paged_patients.page > 1,
        )

        return PagedResponse(
            data=items,
            pagination=pagination,
        )

    async def get(self, patient_id: UUID) -> PatientResponse:
        """Get a patient by ID.

        Parameters
        ----------
        patient_id : UUID
            Patient ID

        Returns
        -------
        PatientResponse
            Patient information

        Raises
        ------
        HTTPException
            404 if patient not found

        """
        patient = await self.patient_repo.get(patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found",
            )
        return PatientResponse.model_validate(patient)

    async def create(self, data: PatientRequest) -> PatientResponse:
        """Create a new patient.

        Parameters
        ----------
        data : PatientRequest
            Patient data to create

        Returns
        -------
        PatientResponse
            Created patient with information

        """
        # Check if patient with same external_id already exists
        if data.external_id:
            existing = await self.patient_repo.get_by_external_id(data.external_id)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Patient with external_id {data.external_id} already exists",
                )

        # Create the patient
        patient = Patient(
            tenant_id=self.tenant_id,
            c_first_name=data.c_first_name,
            c_last_name=data.c_last_name,
            c_address=data.c_address,
            c_phone=data.c_phone,
            birth_date=data.birth_date,
            external_id=data.external_id,
        )

        created_patient = await self.patient_repo.add(patient)
        return PatientResponse.model_validate(created_patient)

    async def update(self, patient_id: UUID, data: PatientRequest) -> PatientResponse:
        """Update a patient.

        Parameters
        ----------
        patient_id : UUID
            ID of patient to update
        data : PatientRequest
            New patient data

        Returns
        -------
        PatientResponse
            Updated patient

        Raises
        ------
        HTTPException
            404 if patient not found
            409 if another patient has same external_id

        """
        patient = await self.patient_repo.get(patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found",
            )

        # Check for external_id conflicts (if changing)
        if data.external_id and data.external_id != patient.external_id:
            existing = await self.patient_repo.get_by_external_id(data.external_id)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Patient with external_id {data.external_id} already exists",
                )

        # Update fields
        patient.c_first_name = data.c_first_name
        patient.c_last_name = data.c_last_name
        patient.c_address = data.c_address
        patient.c_phone = data.c_phone
        patient.birth_date = data.birth_date
        patient.external_id = data.external_id

        updated_patient = await self.patient_repo.update(patient)
        return PatientResponse.model_validate(updated_patient)

    async def delete(self, patient_id: UUID) -> bool:
        """Delete a patient (hard delete).

        Parameters
        ----------
        patient_id : UUID
            ID of patient to delete

        Returns
        -------
        bool
            True if deletion successful

        Raises
        ------
        HTTPException
            404 if patient not found

        """
        patient = await self.patient_repo.get(patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient with ID {patient_id} not found",
            )

        return await self.patient_repo.delete(patient_id)
