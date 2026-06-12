"""Repository pour les événements IoT."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select

from medbox.core.db.models.event import Event
from medbox.core.db.session import async_session_local

ALERT_TYPES = frozenset({"box_offline", "box_error", "maintenance", "error_motor"})


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

    async def list_alerts(
        self,
        tenant_id: uuid.UUID,
        *,
        box_id: uuid.UUID | None = None,
        unacknowledged_only: bool = False,
        limit: int = 100,
    ) -> Sequence[Event]:
        """Liste les événements de type alerte pour un tenant."""
        async with async_session_local() as session:
            stmt = (
                select(Event)
                .where(Event.tenant_id == tenant_id)
                .where(Event.type.in_(ALERT_TYPES))
                .order_by(Event.created_at.desc())
                .limit(limit)
            )
            if box_id:
                stmt = stmt.where(Event.box_id == box_id)
            if unacknowledged_only:
                stmt = stmt.where(Event.acknowledged_at.is_(None))
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get(self, event_id: uuid.UUID, tenant_id: uuid.UUID) -> Event | None:
        async with async_session_local() as session:
            result = await session.execute(
                select(Event)
                .where(Event.id == event_id)
                .where(Event.tenant_id == tenant_id)
            )
            return result.scalar_one_or_none()

    async def acknowledge(
        self, event_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Event | None:
        """Marque une alerte comme acquittée."""
        async with async_session_local() as session:
            result = await session.execute(
                select(Event)
                .where(Event.id == event_id)
                .where(Event.tenant_id == tenant_id)
            )
            event = result.scalar_one_or_none()
            if not event:
                return None
            event.acknowledged_at = datetime.now(tz=UTC)
            await session.commit()
            await session.refresh(event)
            return event
