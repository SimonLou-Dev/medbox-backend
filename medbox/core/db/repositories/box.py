"""Repository pour les boîtiers physiques."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from medbox.core.db.models.box import Box
from medbox.core.db.repositories.base import BaseRepository
from medbox.core.db.session import async_session_local


class BoxRepository(BaseRepository[Box]):
    """Repository Box avec filtrage par tenant."""

    def __init__(self, tenant_id: UUID | None = None) -> None:
        super().__init__(Box)
        self.tenant_id = tenant_id

    async def list(self, with_relations: bool = False) -> Sequence[Box]:
        """Liste toutes les boxes du tenant."""
        if not self.tenant_id:
            msg = "tenant_id requis"
            raise ValueError(msg)

        async with async_session_local() as session:
            stmt = select(self.model).where(self.model.tenant_id == self.tenant_id)
            if with_relations:
                stmt = stmt.options(
                    selectinload(Box.patient),
                    selectinload(Box.wheels),
                )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get(self, box_id: UUID, with_relations: bool = False) -> Box | None:
        """Récupère une box par ID avec vérification tenant."""
        if not self.tenant_id:
            msg = "tenant_id requis"
            raise ValueError(msg)

        async with async_session_local() as session:
            stmt = select(self.model).where(
                (self.model.id == box_id) & (self.model.tenant_id == self.tenant_id),
            )
            if with_relations:
                stmt = stmt.options(
                    selectinload(Box.patient),
                    selectinload(Box.wheels),
                )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_uid(self, box_uid: str) -> Box | None:
        """Récupère une box par son identifiant physique (unique global)."""
        async with async_session_local() as session:
            stmt = select(self.model).where(self.model.box_uid == box_uid)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def create(self, box: Box) -> Box:
        """Crée une nouvelle box."""
        async with async_session_local() as session:
            session.add(box)
            await session.commit()
            await session.refresh(box)
            return box

    async def update(self, box: Box) -> Box:
        """Met à jour une box existante."""
        async with async_session_local() as session:
            merged = await session.merge(box)
            await session.commit()
            await session.refresh(merged)
            return merged
