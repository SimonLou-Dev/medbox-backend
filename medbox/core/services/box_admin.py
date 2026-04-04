"""Service d'administration système pour les boxes (sans scope tenant)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, outerjoin, select

from medbox.core.db.models.box import Box
from medbox.core.db.models.tenant import Tenant
from medbox.core.db.models.wheel import Wheel
from medbox.core.db.repositories.box import BoxRepository
from medbox.core.db.repositories.wheel import WheelRepository
from medbox.core.db.session import async_session_local
from medbox.core.dto.box import BoxResponse
from medbox.core.dto.wheel import WheelResponse

# ---------------------------------------------------------------------------
# DTOs spécifiques admin
# ---------------------------------------------------------------------------


@dataclass
class BoxAdminListItem:
    id: UUID
    box_uid: str
    name: str | None
    status: str
    tenant_id: UUID | None
    tenant_name: str | None
    last_seen_at: str | None


@dataclass
class BoxAdminListResponse:
    items: list[BoxAdminListItem]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class BoxAdminService:
    """Service admin système — opérations sur les boxes sans scope tenant."""

    def __init__(self) -> None:
        self._repo = BoxRepository()

    async def list_all(self, page: int = 1, per_page: int = 20) -> BoxAdminListResponse:
        """Liste toutes les boxes avec infos tenant, paginées."""
        offset = (page - 1) * per_page

        async with async_session_local() as session:
            # COUNT
            total = (
                await session.execute(select(func.count()).select_from(Box))
            ).scalar_one()

            # JOIN boxes → tenants (LEFT OUTER pour boxes sans tenant)
            stmt = (
                select(Box, Tenant.name.label("tenant_name"))
                .select_from(outerjoin(Box, Tenant, Box.tenant_id == Tenant.id))
                .order_by(Box.created_at.desc())
                .offset(offset)
                .limit(per_page)
            )
            rows = (await session.execute(stmt)).all()

        items = [
            BoxAdminListItem(
                id=box.id,
                box_uid=box.box_uid,
                name=box.name,
                status=box.status,
                tenant_id=box.tenant_id,
                tenant_name=tenant_name,
                last_seen_at=box.last_seen_at.isoformat() if box.last_seen_at else None,
            )
            for box, tenant_name in rows
        ]
        return BoxAdminListResponse(
            items=items, total=total, page=page, per_page=per_page
        )

    async def create(self, box_uid: str, name: str | None = None) -> BoxResponse:
        """Crée une box sans tenant."""
        existing = await self._repo.get_by_uid(box_uid)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Une box avec le UID '{box_uid}' existe déjà",
            )
        box = Box(box_uid=box_uid, name=name, status="inactive")
        created = await self._repo.create(box)
        return BoxResponse.from_model(created)

    async def detach_wheel(self, box_uid: str, wheel_id: UUID) -> WheelResponse:
        """Détache une wheel de sa box (status → in_stock)."""
        box = await self._repo.get_by_uid(box_uid)
        if not box:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Box '{box_uid}' introuvable",
            )

        async with async_session_local() as session:
            result = await session.execute(
                select(Wheel).where(Wheel.id == wheel_id, Wheel.box_id == box.id)
            )
            wheel = result.scalar_one_or_none()

        if not wheel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Wheel {wheel_id} introuvable sur cette box",
            )

        wheel.box_id = None
        wheel.status = "in_stock"
        wheel_repo = WheelRepository()
        updated = await wheel_repo.update(wheel)
        return WheelResponse.from_model(updated)

    async def delete_wheel(self, box_uid: str, wheel_id: UUID) -> None:
        """Supprime définitivement une wheel."""
        box = await self._repo.get_by_uid(box_uid)
        if not box:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Box '{box_uid}' introuvable",
            )

        async with async_session_local() as session:
            result = await session.execute(
                select(Wheel).where(Wheel.id == wheel_id, Wheel.box_id == box.id)
            )
            wheel = result.scalar_one_or_none()
            if not wheel:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Wheel {wheel_id} introuvable sur cette box",
                )
            await session.delete(wheel)
            await session.commit()

    async def adopt(self, box_uid: str, tenant_id: UUID) -> BoxResponse:
        """Rattache une box à un tenant."""
        box = await self._repo.get_by_uid(box_uid)
        if not box:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Box '{box_uid}' introuvable",
            )
        if box.tenant_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cette box est déjà rattachée à un tenant",
            )
        box.tenant_id = tenant_id
        box.status = "active"
        updated = await self._repo.update(box)
        return BoxResponse.from_model(updated)

    async def unadopt(self, box_id: UUID, tenant_id: UUID) -> BoxResponse:
        """Détache une box de son tenant."""
        repo = BoxRepository(tenant_id=tenant_id)
        box = await repo.get(box_id)
        if not box:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Box {box_id} introuvable dans ce tenant",
            )
        box.tenant_id = None
        box.status = "inactive"
        updated = await self._repo.update(box)
        return BoxResponse.from_model(updated)
