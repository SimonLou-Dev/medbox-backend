"""Repository pour les entrées de télémétrie."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from medbox.core.db.models.telemetry import Telemetry
from medbox.core.db.session import async_session_local


class TelemetryRepository:
    """Accès aux données de télémétrie."""

    async def add(self, entry: Telemetry) -> Telemetry:
        async with async_session_local() as session:
            session.add(entry)
            await session.commit()
            await session.refresh(entry)
            return entry

    async def list_by_box(
        self,
        box_id: uuid.UUID,
        *,
        metric: str | None = None,
        limit: int = 100,
    ) -> Sequence[Telemetry]:
        async with async_session_local() as session:
            stmt = (
                select(Telemetry)
                .where(Telemetry.box_id == box_id)
                .order_by(Telemetry.created_at.desc())
                .limit(limit)
            )
            if metric:
                stmt = stmt.where(Telemetry.metric == metric)
            result = await session.execute(stmt)
            return result.scalars().all()
