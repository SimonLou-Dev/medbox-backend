"""Service d'administration système pour les wheels (sans scope tenant)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select

from medbox.core.db.models.wheel import Wheel
from medbox.core.db.models.wheel_slot import WheelSlot
from medbox.core.db.repositories.wheel import WheelRepository
from medbox.core.db.session import async_session_local
from medbox.core.dto.wheel import WheelResponse


@dataclass
class WheelAdminListItem:
    id: UUID
    wheel_uid: str
    slot_count: int
    status: str
    tenant_id: UUID | None
    tenant_name: str | None
    box_id: UUID | None
    box_uid: str | None


@dataclass
class WheelAdminListResponse:
    items: list[WheelAdminListItem]
    total: int
    page: int
    per_page: int


class WheelAdminService:
    """Service admin système — opérations sur les wheels sans scope tenant."""

    def __init__(self) -> None:
        self._repo = WheelRepository()

    async def list_all(self, page: int = 1, per_page: int = 20) -> WheelAdminListResponse:
        """Liste toutes les wheels avec infos tenant et box, paginées."""
        total, rows = await self._repo.list_all_paginated(page=page, per_page=per_page)
        items = [
            WheelAdminListItem(
                id=wheel.id,
                wheel_uid=wheel.wheel_uid,
                slot_count=wheel.slot_count,
                status=wheel.status,
                tenant_id=wheel.tenant_id,
                tenant_name=tenant_name,
                box_id=wheel.box_id,
                box_uid=box_uid_label,
            )
            for wheel, tenant_name, box_uid_label in rows
        ]
        return WheelAdminListResponse(items=items, total=total, page=page, per_page=per_page)

    async def create(self, wheel_uid: str, slot_count: int = 28) -> WheelResponse:
        """Crée une wheel sans tenant ni box."""
        existing = await self._repo.get_by_uid(wheel_uid)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Une wheel avec le UID '{wheel_uid}' existe déjà",
            )
        wheel = Wheel(wheel_uid=wheel_uid, slot_count=slot_count, status="in_stock")
        wheel.slots = [WheelSlot(index=i) for i in range(slot_count)]
        created = await self._repo.create(wheel)
        loaded = await self._repo.get_global(created.id, with_slots=True)
        return WheelResponse.from_model(loaded)

    async def detach(self, wheel_id: UUID) -> WheelResponse:
        """Détache une wheel de sa box (box_id → None, status → in_stock)."""
        wheel = await self._repo.get_global(wheel_id)
        if not wheel:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Wheel {wheel_id} introuvable")
        wheel.box_id = None
        wheel.status = "in_stock"
        updated = await self._repo.update(wheel)
        return WheelResponse.from_model(updated)

    async def delete(self, wheel_id: UUID) -> None:
        """Supprime définitivement une wheel et ses slots."""
        async with async_session_local() as session:
            result = await session.execute(select(Wheel).where(Wheel.id == wheel_id))
            wheel = result.scalar_one_or_none()
            if not wheel:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Wheel {wheel_id} introuvable")
            await session.delete(wheel)
            await session.commit()

    async def adopt(self, wheel_uid: str, tenant_id: UUID) -> WheelResponse:
        """Rattache une wheel à un tenant."""
        wheel = await self._repo.get_by_uid(wheel_uid)
        if not wheel:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Wheel '{wheel_uid}' introuvable")
        if wheel.tenant_id is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cette wheel est déjà rattachée à un tenant")
        wheel.tenant_id = tenant_id
        wheel.status = "prepared"
        updated = await self._repo.update(wheel)
        return WheelResponse.from_model(updated)

    async def unadopt(self, wheel_id: UUID, tenant_id: UUID) -> WheelResponse:
        """Détache une wheel de son tenant."""
        wheel = await WheelRepository(tenant_id=tenant_id).get(wheel_id)
        if not wheel:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Wheel {wheel_id} introuvable dans ce tenant")
        wheel.tenant_id = None
        wheel.box_id = None
        wheel.status = "in_stock"
        updated = await self._repo.update(wheel)
        return WheelResponse.from_model(updated)

    async def mount(self, wheel_id: UUID, box_id: UUID, tenant_id: UUID) -> WheelResponse:
        """Monte une wheel sur une box (vérifie que la box appartient au tenant)."""
        from medbox.core.db.repositories.box import BoxRepository
        box = await BoxRepository(tenant_id=tenant_id).get(box_id)
        if not box:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Box {box_id} introuvable dans ce tenant")
        wheel = await WheelRepository(tenant_id=tenant_id).get(wheel_id)
        if not wheel:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Wheel {wheel_id} introuvable dans ce tenant")
        wheel.box_id = box_id
        wheel.status = "mounted"
        updated = await self._repo.update(wheel)
        return WheelResponse.from_model(updated)

    async def unmount(self, wheel_id: UUID, tenant_id: UUID) -> WheelResponse:
        """Démonte une wheel de sa box."""
        wheel = await WheelRepository(tenant_id=tenant_id).get(wheel_id)
        if not wheel:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Wheel {wheel_id} introuvable dans ce tenant")
        wheel.box_id = None
        wheel.status = "prepared"
        updated = await self._repo.update(wheel)
        return WheelResponse.from_model(updated)
