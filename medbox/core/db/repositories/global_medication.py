"""Repository for Global Medication database access.

Handles all database queries for medications from the French BDPM.
"""

from __future__ import annotations

from sqlalchemy import func, or_, select

from medbox.core.db.models.global_medication import GlobalMedication
from medbox.core.db.repositories.base import BaseRepository
from medbox.core.db.session import async_session_local


class GlobalMedicationRepository(BaseRepository[GlobalMedication]):
    """Repository for Global Medication database operations.

    Provides CRUD operations and search functionality for medications
    from the French BDPM database.
    """

    def __init__(self) -> None:
        """Initialize repository.

        Uses async_session_local for database connections.

        """
        super().__init__(GlobalMedication)

    async def get_by_cis(self, cis: int) -> GlobalMedication | None:
        """Get medication by CIS code.

        Parameters
        ----------
        cis : int
            CIS Code (Code Identifiant de Spécialité)

        Returns
        -------
        GlobalMedication | None
            Medication if found, None otherwise

        """
        async with async_session_local() as session:
            stmt = select(self.model).where(self.model.cis == cis)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def search(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[GlobalMedication], int]:
        """Search medications by name or manufacturer.

        Performs full-text search on:
        - element_pharmaceutique (product name)
        - titulaire (manufacturer)

        Parameters
        ----------
        query : str
            Search query string
        limit : int
            Maximum results to return
        offset : int
            Number of results to skip

        Returns
        -------
        tuple[list[GlobalMedication], int]
            Tuple of (medications list, total count)

        """
        async with async_session_local() as session:
            # Convert query to lowercase for case-insensitive search
            query_lower = f"%{query.lower()}%"

            # Build search condition: match in name OR manufacturer
            search_condition = or_(
                func.lower(self.model.element_pharmaceutique).ilike(query_lower),
                func.lower(self.model.titulaire).ilike(query_lower),
            )

            # Count total matching results
            count_stmt = (
                select(func.count()).select_from(self.model).where(search_condition)
            )
            count_result = await session.execute(count_stmt)
            total = count_result.scalar()

            # Fetch paginated results
            stmt = (
                select(self.model)
                .where(search_condition)
                .order_by(self.model.element_pharmaceutique)
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            medications = result.scalars().all()

            return medications, total

    async def list_all(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[GlobalMedication], int]:
        """List all medications with pagination.

        Parameters
        ----------
        limit : int
            Maximum results to return
        offset : int
            Number of results to skip

        Returns
        -------
        tuple[list[GlobalMedication], int]
            Tuple of (medications list, total count)

        """
        async with async_session_local() as session:
            # Count total medications
            count_stmt = select(func.count()).select_from(self.model)
            count_result = await session.execute(count_stmt)
            total = count_result.scalar()

            # Fetch paginated results
            stmt = (
                select(self.model)
                .order_by(self.model.element_pharmaceutique)
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            medications = result.scalars().all()

            return medications, total

    async def count_total(self) -> int:
        """Get total count of medications in database.

        Returns
        -------
        int
            Total number of medications

        """
        async with async_session_local() as session:
            stmt = select(func.count()).select_from(self.model)
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def upsert_medication(
        self,
        medication: GlobalMedication,
    ) -> GlobalMedication:
        """Insert or update medication by CIS (upsert).

        Safely handles concurrent inserts by checking if medication exists
        before inserting. If it already exists, updates sync_date.

        Parameters
        ----------
        medication : GlobalMedication
            Medication to insert or update

        Returns
        -------
        GlobalMedication
            The medication (inserted or existing with updated sync_date)

        """
        from datetime import datetime

        async with async_session_local() as session:
            # First, check if medication already exists
            stmt = select(self.model).where(self.model.cis == medication.cis)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Update sync_date for existing medication
                existing.sync_date = datetime.now()
                existing.updated_at = datetime.now()
                await session.merge(existing)
                await session.commit()
                await session.refresh(existing)
                return existing

            # Medication doesn't exist, insert it
            session.add(medication)
            await session.commit()
            await session.refresh(medication)

            return medication
