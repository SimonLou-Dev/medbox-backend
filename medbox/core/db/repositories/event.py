"""Repository pour les événements IoT."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from medbox.core.db.models.event import Event
from medbox.core.db.session import async_session_local


class EventRepository:
    """Accès aux données d'événements."""

    async def add(self, entry: Event) -> Event:
        async with async_session_local() as session:
            session.add(entry)
            await session.commit()
            await session.refresh(entry)
            return entry

    async def list_by_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        box_id: uuid.UUID | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> Sequence[Event]:
        async with async_session_local() as session:
            stmt = (
                select(Event)
                .where(Event.tenant_id == tenant_id)
                .order_by(Event.created_at.desc())
                .limit(limit)
            )
            if box_id:
                stmt = stmt.where(Event.box_id == box_id)
            if event_type:
                stmt = stmt.where(Event.type == event_type)
            result = await session.execute(stmt)
            return result.scalars().all()
