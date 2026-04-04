"""Repository pour les items de planning de prescription."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

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

    async def list_by_prescription(
        self,
        prescription_id: UUID,
    ) -> Sequence[PrescriptionScheduleItem]:
        """Liste tous les items planifiés d'une prescription."""
        async with async_session_local() as session:
            stmt = (
                select(self.model)
                .where(self.model.prescription_id == prescription_id)
                .order_by(self.model.scheduled_at)
            )
            if self.tenant_id:
                stmt = stmt.where(self.model.tenant_id == self.tenant_id)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def list_due(
        self,
        now: datetime | None = None,
    ) -> Sequence[PrescriptionScheduleItem]:
        """Retourne les items en attente dont l'heure de prise est dépassée.

        Utilisé par le scheduler pour déclencher les distributions.
        """
        cutoff = now or datetime.now(tz=UTC)
        async with async_session_local() as session:
            stmt = (
                select(self.model)
                .where(self.model.status == "pending")
                .where(self.model.scheduled_at <= cutoff)
                .order_by(self.model.scheduled_at)
            )
            if self.tenant_id:
                stmt = stmt.where(self.model.tenant_id == self.tenant_id)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def list_pending_by_box(
        self,
        box_id: UUID,
    ) -> Sequence[PrescriptionScheduleItem]:
        """Liste les items pending pour une box donnée."""
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
        dispatched_at: datetime | None = None,
        taken_at: datetime | None = None,
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
            if dispatched_at is not None:
                item.dispatched_at = dispatched_at
            if taken_at is not None:
                item.taken_at = taken_at
            if error_reason is not None:
                item.error_reason = error_reason

            await session.commit()
            await session.refresh(item)
            return item
