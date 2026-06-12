"""Repository pour les items de planning de prescription."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from medbox.core.db.models.prescription_schedule_item import PrescriptionScheduleItem
from medbox.core.db.repositories.base import BaseRepository
from medbox.core.db.session import async_session_local


class PrescriptionScheduleItemRepository(BaseRepository[PrescriptionScheduleItem]):
    """Repository pour PrescriptionScheduleItem, scopé par tenant."""

    def __init__(self, tenant_id: UUID | None = None) -> None:
        super().__init__(PrescriptionScheduleItem)
        self.tenant_id = tenant_id

    async def create(self, item: PrescriptionScheduleItem) -> PrescriptionScheduleItem:
        """Persiste un nouvel item de planning."""
        async with async_session_local() as session:
            session.add(item)
            await session.commit()
            await session.refresh(item)
            return item

    async def create_many(
        self,
        items: list[PrescriptionScheduleItem],
    ) -> list[PrescriptionScheduleItem]:
        """Persiste plusieurs items en une seule transaction."""
        async with async_session_local() as session:
            session.add_all(items)
            await session.commit()
            for item in items:
                await session.refresh(item)
            return items

    async def list_by_plan(
        self,
        plan_id: UUID,
    ) -> Sequence[PrescriptionScheduleItem]:
        """Liste tous les items d'un plan de chargement, triés par heure."""
        async with async_session_local() as session:
            stmt = (
                select(self.model)
                .where(self.model.wheel_load_plan_id == plan_id)
                .options(selectinload(self.model.wheel_slot))
                .order_by(self.model.scheduled_at)
            )
            if self.tenant_id:
                stmt = stmt.where(self.model.tenant_id == self.tenant_id)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def list_upcoming_by_box(
        self,
        box_id: UUID,
        limit: int = 3,
    ) -> Sequence[PrescriptionScheduleItem]:
        """Retourne les N prochaines distributions pending pour une box.

        Utilisé par le job preload pour alimenter la medbox 2x/jour.
        """
        from datetime import UTC, datetime

        now = datetime.now(tz=UTC)
        async with async_session_local() as session:
            stmt = (
                select(self.model)
                .where(self.model.box_id == box_id)
                .where(self.model.status == "pending")
                .where(self.model.scheduled_at >= now)
                .options(selectinload(self.model.wheel_slot))
                .order_by(self.model.scheduled_at)
                .limit(limit)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def list_pending_by_box(
        self,
        box_id: UUID,
    ) -> Sequence[PrescriptionScheduleItem]:
        """Liste tous les items pending pour une box."""
        async with async_session_local() as session:
            stmt = (
                select(self.model)
                .where(self.model.box_id == box_id)
                .where(self.model.status == "pending")
                .order_by(self.model.scheduled_at)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def update_status(
        self,
        item_id: UUID,
        status: str,
        *,
        taken_at=None,
        error_reason: str | None = None,
    ) -> PrescriptionScheduleItem | None:
        """Met à jour le statut d'un item."""
        async with async_session_local() as session:
            stmt = select(self.model).where(self.model.id == item_id)
            result = await session.execute(stmt)
            item = result.scalar_one_or_none()
            if not item:
                return None

            item.status = status
            if taken_at is not None:
                item.taken_at = taken_at
            if error_reason is not None:
                item.error_reason = error_reason

            await session.commit()
            await session.refresh(item)
            return item
