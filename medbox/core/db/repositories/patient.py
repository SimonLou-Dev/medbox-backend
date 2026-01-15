"""Repository for patients."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import select

from medbox.core.db.models.patient import Patient
from medbox.core.db.repositories.base import BaseRepository, Page
from medbox.core.db.session import async_session_local


class PatientRepository(BaseRepository[Patient]):
    """Patient repository with tenant scoping."""

    def __init__(self, tenant_id: UUID | None = None) -> None:
        """Initialize repository.

        Parameters
        ----------
        tenant_id : UUID | None
            Tenant ID for data scoping (mandatory for all access).

        """
        super().__init__(Patient)
        self.tenant_id = tenant_id

    async def list(self) -> Sequence[Patient]:
        """Get all patients for the tenant.

        Returns
        -------
        Sequence[Patient]
            List of patients for the tenant.

        """
        if not self.tenant_id:
            msg = "tenant_id is required for patient queries"
            raise ValueError(msg)

        async with async_session_local() as session:
            stmt = select(self.model).where(self.model.tenant_id == self.tenant_id)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get(
        self,
        patient_id: UUID,
        relationships: list[str] | None = None,
    ) -> Patient | None:
        """Get a patient by ID with tenant verification.

        Parameters
        ----------
        patient_id : UUID
            Patient ID
        relationships : list[str] | None
            Relations to load (eager loading)

        Returns
        -------
        Patient | None
            Patient if found, None otherwise.

        """
        if not self.tenant_id:
            msg = "tenant_id is required for patient queries"
            raise ValueError(msg)

        async with async_session_local() as session:
            stmt = select(self.model).where(
                (self.model.id == patient_id)
                & (self.model.tenant_id == self.tenant_id),
            )
            result = await session.execute(stmt)
            return result.scalars().first()

    async def get_by_external_id(self, external_id: str) -> Patient | None:
        """Get a patient by external ID.

        Parameters
        ----------
        external_id : str
            External ID (EHR, DPI)

        Returns
        -------
        Patient | None
            Patient if found, None otherwise.

        """
        if not self.tenant_id:
            msg = "tenant_id is required for patient queries"
            raise ValueError(msg)

        async with async_session_local() as session:
            stmt = select(self.model).where(
                (self.model.external_id == external_id)
                & (self.model.tenant_id == self.tenant_id),
            )
            result = await session.execute(stmt)
            return result.scalars().first()

    async def paginate(
        self,
        *,
        filters: Mapping[str, Any] | None = None,
        page: int = 1,
        per_page: int = 20,
        search: str | None = None,
        sort_by: str = "c_last_name",
        sort_order: str = "asc",
        relations: list[str] | None = None,
    ) -> Page[Patient]:
        """Get a page of patients for the tenant.

        Parameters
        ----------
        filters : Mapping[str, Any] | None
            Additional filters
        page : int
            Page number (>= 1)
        per_page : int
            Items per page
        search : str | None
            Search term for first_name or last_name
        sort_by : str
            Field to sort by: c_first_name, c_last_name, birth_date (default c_last_name)
        sort_order : str
            Sort order: asc or desc (default asc)
        relations : list[str] | None
            Relations to load

        Returns
        -------
        Page[Patient]
            Page of patients

        """
        if not self.tenant_id:
            msg = "tenant_id is required for patient queries"
            raise ValueError(msg)

        offset = (page - 1) * per_page
        filters = filters or {}

        async with async_session_local() as session:
            # Base query with tenant filtering
            stmt = select(self.model).where(self.model.tenant_id == self.tenant_id)

            # Apply additional filters
            if filters:
                conditions = []
                for field, value in filters.items():
                    attr = getattr(self.model, field, None)
                    if attr is None:
                        msg = f"Unknown field in model: {field}"
                        raise ValueError(msg)
                    conditions.append(attr == value)
                stmt = stmt.filter(*conditions)

            # Apply search filter (search is done in memory after decryption)
            # For now, we fetch all and filter
            stmt = self._apply_relations(stmt, relations)

            # Execute query to get all matching items
            result = await session.execute(stmt)
            all_items = result.scalars().all()

            # Filter by search term (applied to decrypted fields)
            if search:
                search_lower = search.lower()
                all_items = [
                    item
                    for item in all_items
                    if (
                        search_lower in item.c_first_name.lower()
                        or search_lower in item.c_last_name.lower()
                    )
                ]

            # Sort items
            reverse = sort_order.lower() == "desc"
            if sort_by == "c_first_name":
                all_items = sorted(
                    all_items,
                    key=lambda x: x.c_first_name.lower(),
                    reverse=reverse,
                )
            elif sort_by == "c_last_name":
                all_items = sorted(
                    all_items,
                    key=lambda x: x.c_last_name.lower(),
                    reverse=reverse,
                )
            elif sort_by == "birth_date":
                all_items = sorted(
                    all_items,
                    key=lambda x: x.birth_date or "",
                    reverse=reverse,
                )

            # Calculate total before pagination
            total = len(all_items)

            # Apply pagination
            paginated_items = all_items[offset : offset + per_page]

            # Calculate number of pages
            total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0

            return Page(
                items=paginated_items,
                page=page,
                per_page=per_page,
                total=total,
                total_pages=total_pages,
            )
