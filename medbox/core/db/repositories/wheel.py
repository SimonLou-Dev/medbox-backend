"""Repository pour les roues et leurs compartiments."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from medbox.core.db.models.wheel import Wheel
from medbox.core.db.models.wheel_slot import WheelSlot
from medbox.core.db.repositories.base import BaseRepository
from medbox.core.db.session import async_session_local


class WheelRepository(BaseRepository[Wheel]):
    """Repository Wheel avec filtrage par tenant."""

    def __init__(self, tenant_id: UUID | None = None) -> None:
        super().__init__(Wheel)
        self.tenant_id = tenant_id

    async def list(self, with_slots: bool = False) -> Sequence[Wheel]:
        """Liste toutes les roues du tenant."""
        if not self.tenant_id:
            msg = "tenant_id requis"
            raise ValueError(msg)

        async with async_session_local() as session:
            stmt = select(self.model).where(self.model.tenant_id == self.tenant_id)
            if with_slots:
                stmt = stmt.options(selectinload(Wheel.slots))
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get(self, wheel_id: UUID, with_slots: bool = False) -> Wheel | None:
        """Récupère une roue par ID avec vérification tenant."""
        if not self.tenant_id:
            msg = "tenant_id requis"
            raise ValueError(msg)

        async with async_session_local() as session:
            stmt = select(self.model).where(
                (self.model.id == wheel_id) & (self.model.tenant_id == self.tenant_id),
            )
            if with_slots:
                stmt = stmt.options(selectinload(Wheel.slots))
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_uid(self, wheel_uid: str) -> Wheel | None:
        """Récupère une roue par son identifiant physique (unique global)."""
        async with async_session_local() as session:
            stmt = select(self.model).where(self.model.wheel_uid == wheel_uid)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def create(self, wheel: Wheel) -> Wheel:
        """Crée une nouvelle roue (et génère ses slots si demandé)."""
        async with async_session_local() as session:
            session.add(wheel)
            await session.commit()
            await session.refresh(wheel)
            return wheel

    async def update(self, wheel: Wheel) -> Wheel:
        """Met à jour une roue existante."""
        async with async_session_local() as session:
            merged = await session.merge(wheel)
            await session.commit()
            await session.refresh(merged)
            return merged

    async def get_slot(self, slot_id: UUID) -> WheelSlot | None:
        """Récupère un slot par son ID."""
        async with async_session_local() as session:
            stmt = select(WheelSlot).where(WheelSlot.id == slot_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def update_slot(self, slot: WheelSlot) -> WheelSlot:
        """Met à jour un slot existant."""
        async with async_session_local() as session:
            merged = await session.merge(slot)
            await session.commit()
            await session.refresh(merged)
            return merged

    async def list_slots(self, wheel_id: UUID) -> Sequence[WheelSlot]:
        """Liste tous les slots d'une roue."""
        async with async_session_local() as session:
            stmt = select(WheelSlot).where(WheelSlot.wheel_id == wheel_id)
            result = await session.execute(stmt)
            return result.scalars().all()
