"""Repository for prescriptions."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from medbox.core.db.models.prescription import Prescription
from medbox.core.db.repositories.base import BaseRepository, Page
from medbox.core.db.session import async_session_local


class PrescriptionRepository(BaseRepository[Prescription]):
    """Prescription repository with tenant scoping."""

    def __init__(self, tenant_id: UUID | None = None) -> None:
        """Initialize repository.

        Parameters
        ----------
        tenant_id : UUID | None
            Tenant ID for data scoping (mandatory for all access).
        """
        super().__init__(Prescription)
        self.tenant_id = tenant_id

    async def list(
        self,
        relations: list[str] | None = None,
    ) -> Sequence[Prescription]:
        """Get all prescriptions for the tenant.

        Parameters
        ----------
        relations : list[str] | None
            Relations to load (eager loading)

        Returns
        -------
        Sequence[Prescription]
            List of prescriptions for the tenant.
        """
        if not self.tenant_id:
            msg = "tenant_id is required for prescription queries"
            raise ValueError(msg)

        async with async_session_local() as session:
            stmt = select(self.model).where(self.model.tenant_id == self.tenant_id)
            stmt = self._apply_relations(stmt, relations)
            result = await session.execute(stmt)
            return result.scalars().unique().all()

    async def get(
        self,
        prescription_id: UUID,
        relations: list[str] | None = None,
    ) -> Prescription | None:
        """Get a prescription by ID with tenant verification.

        Parameters
        ----------
        prescription_id : UUID
            Prescription ID
        relations : list[str] | None
            Relations to load (eager loading) e.g. ["items", "items.medication", "patient"]

        Returns
        -------
        Prescription | None
            Prescription if found, None otherwise.
        """
        if not self.tenant_id:
            msg = "tenant_id is required for prescription queries"
            raise ValueError(msg)

        async with async_session_local() as session:
            stmt = select(self.model).where(
                (self.model.id == prescription_id)
                & (self.model.tenant_id == self.tenant_id),
            )
            stmt = self._apply_relations(stmt, relations)
            result = await session.execute(stmt)
            return result.scalars().unique().first()

    async def get_by_patient(
        self,
        patient_id: UUID,
        relations: list[str] | None = None,
    ) -> Sequence[Prescription]:
        """Get all prescriptions for a patient.

        Parameters
        ----------
        patient_id : UUID
            Patient ID
        relations : list[str] | None
            Relations to load (eager loading)

        Returns
        -------
        Sequence[Prescription]
            List of prescriptions for the patient.
        """
        if not self.tenant_id:
            msg = "tenant_id is required for prescription queries"
            raise ValueError(msg)

        async with async_session_local() as session:
            stmt = select(self.model).where(
                (self.model.patient_id == patient_id)
                & (self.model.tenant_id == self.tenant_id),
            )
            stmt = self._apply_relations(stmt, relations)
            result = await session.execute(stmt)
            return result.scalars().unique().all()

    async def paginate_by_patient(
        self,
        patient_id: UUID,
        *,
        page: int = 1,
        per_page: int = 20,
        status: str | None = None,
        relations: list[str] | None = None,
    ) -> Page[Prescription]:
        """Get paginated prescriptions for a patient.

        Parameters
        ----------
        patient_id : UUID
            Patient ID
        page : int
            Page number (1-indexed)
        per_page : int
            Items per page
        status : str | None
            Filter by status (active/paused/stopped/expired)
        relations : list[str] | None
            Relations to load (eager loading)

        Returns
        -------
        Page[Prescription]
            Paginated results with metadata.
        """
        if not self.tenant_id:
            msg = "tenant_id is required for prescription queries"
            raise ValueError(msg)

        filters = {
            "patient_id": patient_id,
            "tenant_id": self.tenant_id,
        }
        if status:
            filters["status"] = status

        return await self.paginate(
            filters=filters,
            page=page,
            per_page=per_page,
            relations=relations,
        )

    async def list_by_status(
        self,
        status: str,
        relations: list[str] | None = None,
    ) -> Sequence[Prescription]:
        """Get prescriptions by status for tenant.

        Parameters
        ----------
        status : str
            Status filter (active/paused/stopped/expired)
        relations : list[str] | None
            Relations to load (eager loading)

        Returns
        -------
        Sequence[Prescription]
            List of prescriptions matching the status.
        """
        if not self.tenant_id:
            msg = "tenant_id is required for prescription queries"
            raise ValueError(msg)

        async with async_session_local() as session:
            stmt = select(self.model).where(
                (self.model.status == status)
                & (self.model.tenant_id == self.tenant_id),
            )
            stmt = self._apply_relations(stmt, relations)
            result = await session.execute(stmt)
            return result.scalars().unique().all()

    async def create(self, prescription: Prescription) -> Prescription:
        """Create a prescription.

        Parameters
        ----------
        prescription : Prescription
            Prescription instance to create

        Returns
        -------
        Prescription
            Created prescription

        Raises
        ------
        HTTPException
            If integrity constraint violated
        """
        return await self.add(prescription)

    async def update(self, prescription: Prescription) -> Prescription:
        """Update a prescription using merge pattern for detached objects.

        Parameters
        ----------
        prescription : Prescription
            Prescription instance to update

        Returns
        -------
        Prescription
            Updated prescription

        Raises
        ------
        HTTPException
            If integrity constraint violated
        """
        async with async_session_local() as session:
            # Use merge() for detached objects (important!)
            merged = await session.merge(prescription)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise HTTPException(
                    400,
                    "Update failed: constraint violation",
                ) from exc
            await session.refresh(merged)
            return merged
