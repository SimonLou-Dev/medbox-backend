"""Repository pour les plans de chargement de roue."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from medbox.core.db.models.wheel_load_plan import WheelLoadPlan
from medbox.core.db.repositories.base import BaseRepository
from medbox.core.db.session import async_session_local


class WheelLoadPlanRepository(BaseRepository[WheelLoadPlan]):
    """Repository pour WheelLoadPlan, scopé par tenant."""

    def __init__(self, tenant_id: UUID) -> None:
        super().__init__(WheelLoadPlan)
        self.tenant_id = tenant_id

    async def create(self, plan: WheelLoadPlan) -> WheelLoadPlan:
        """Persiste un nouveau plan."""
        async with async_session_local() as session:
            session.add(plan)
            await session.commit()
            await session.refresh(plan)
            return plan

    async def get(self, plan_id: UUID) -> WheelLoadPlan | None:
        """Récupère un plan avec ses relations (prescriptions, wheel, box)."""
        async with async_session_local() as session:
            stmt = (
                select(WheelLoadPlan)
                .where(WheelLoadPlan.id == plan_id)
                .where(WheelLoadPlan.tenant_id == self.tenant_id)
                .options(
                    selectinload(WheelLoadPlan.prescriptions),
                    selectinload(WheelLoadPlan.wheel),
                    selectinload(WheelLoadPlan.box),
                )
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_by_tenant(self) -> Sequence[WheelLoadPlan]:
        """Liste tous les plans du tenant."""
        async with async_session_local() as session:
            stmt = (
                select(WheelLoadPlan)
                .where(WheelLoadPlan.tenant_id == self.tenant_id)
                .order_by(WheelLoadPlan.created_at.desc())
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def update(self, plan: WheelLoadPlan) -> WheelLoadPlan:
        """Sauvegarde les modifications d'un plan."""
        async with async_session_local() as session:
            merged = await session.merge(plan)
            await session.commit()
            await session.refresh(merged)
            return merged
