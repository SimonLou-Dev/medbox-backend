"""Service de gestion des roues et de leurs compartiments."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from medbox.core.db.models.wheel import Wheel
from medbox.core.db.models.wheel_slot import WheelSlot
from medbox.core.db.repositories.wheel import WheelRepository
from medbox.core.dto.wheel import (
    WheelRequest,
    WheelResponse,
    WheelSlotResponse,
    WheelSlotUpdateRequest,
    WheelStatsResponse,
    WheelStatusUpdateRequest,
)


class WheelService:
    """Service CRUD pour les Wheel et WheelSlot, scoped par tenant."""

    def __init__(
        self,
        tenant_id: UUID,
        wheel_repo: WheelRepository | None = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.wheel_repo = wheel_repo or WheelRepository(tenant_id=tenant_id)

    async def get_stats(self) -> WheelStatsResponse:
        """Statistiques agrégées des roues du tenant."""
        data = await self.wheel_repo.get_stats()
        return WheelStatsResponse(**data)

    async def list(self) -> list[WheelResponse]:
        """Liste toutes les roues du tenant (avec leurs slots)."""
        wheels = await self.wheel_repo.list(with_slots=True)
        return [WheelResponse.from_model(w) for w in wheels]

    async def list_paginated(
        self,
        page: int = 1,
        per_page: int = 20,
        status: str | None = None,
    ) -> tuple[int, list[WheelResponse]]:
        """Liste paginée avec filtre optionnel de statut."""
        total, wheels = await self.wheel_repo.list_paginated(
            page=page, per_page=per_page, with_slots=True, status=status
        )
        return total, [WheelResponse.from_model(w) for w in wheels]

    async def get(self, wheel_id: UUID) -> WheelResponse:
        """Récupère une roue par ID (avec ses slots).

        Raises
        ------
        HTTPException 404 si non trouvée.

        """
        wheel = await self.wheel_repo.get(wheel_id, with_slots=True)
        if not wheel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Roue {wheel_id} introuvable",
            )
        return WheelResponse.from_model(wheel)

    async def create(self, data: WheelRequest) -> WheelResponse:
        """Crée une nouvelle roue et génère automatiquement ses slots.

        Raises
        ------
        HTTPException 409 si wheel_uid déjà utilisé.

        """
        existing = await self.wheel_repo.get_by_uid(data.wheel_uid)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Une roue avec le UID '{data.wheel_uid}' existe déjà",
            )

        wheel = Wheel(
            tenant_id=self.tenant_id,
            wheel_uid=data.wheel_uid,
            patient_id=data.patient_id,
            box_id=data.box_id,
            slot_count=data.slot_count,
            status=data.status,
        )
        # Génération des slots (wheel_id sera injecté par SQLAlchemy via la relation)
        wheel.slots = [WheelSlot(index=i) for i in range(data.slot_count)]

        created = await self.wheel_repo.create(wheel)
        # Recharger avec les slots
        created_with_slots = await self.wheel_repo.get(created.id, with_slots=True)
        return WheelResponse.from_model(created_with_slots)

    async def update(self, wheel_id: UUID, data: WheelRequest) -> WheelResponse:
        """Met à jour une roue (sans recréer les slots).

        Raises
        ------
        HTTPException 404 si non trouvée.
        HTTPException 409 si wheel_uid déjà pris.

        """
        wheel = await self.wheel_repo.get(wheel_id, with_slots=True)
        if not wheel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Roue {wheel_id} introuvable",
            )

        if data.wheel_uid != wheel.wheel_uid:
            existing = await self.wheel_repo.get_by_uid(data.wheel_uid)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Une roue avec le UID '{data.wheel_uid}' existe déjà",
                )

        wheel.wheel_uid = data.wheel_uid
        wheel.patient_id = data.patient_id
        wheel.box_id = data.box_id
        wheel.status = data.status

        updated = await self.wheel_repo.update(wheel)
        updated_with_slots = await self.wheel_repo.get(updated.id, with_slots=True)
        return WheelResponse.from_model(updated_with_slots)

    async def update_status(
        self,
        wheel_id: UUID,
        data: WheelStatusUpdateRequest,
    ) -> WheelResponse:
        """Met à jour uniquement le statut d'une roue."""
        wheel = await self.wheel_repo.get(wheel_id)
        if not wheel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Roue {wheel_id} introuvable",
            )
        wheel.status = data.status
        await self.wheel_repo.update(wheel)
        updated_with_slots = await self.wheel_repo.get(wheel_id, with_slots=True)
        return WheelResponse.from_model(updated_with_slots)

    async def delete(self, wheel_id: UUID) -> bool:
        """Supprime une roue (cascade sur les slots).

        Raises
        ------
        HTTPException 404 si non trouvée.

        """
        wheel = await self.wheel_repo.get(wheel_id)
        if not wheel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Roue {wheel_id} introuvable",
            )
        return await self.wheel_repo.delete(wheel_id)

    # ------------------------------------------------------------------
    # Gestion des slots
    # ------------------------------------------------------------------

    async def list_slots(self, wheel_id: UUID) -> list[WheelSlotResponse]:
        """Liste tous les slots d'une roue."""
        wheel = await self.wheel_repo.get(wheel_id)
        if not wheel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Roue {wheel_id} introuvable",
            )
        slots = await self.wheel_repo.list_slots(wheel_id)
        return [WheelSlotResponse.from_model(s) for s in slots]

    async def get_slot(self, wheel_id: UUID, slot_id: UUID) -> WheelSlotResponse:
        """Récupère un slot par ID avec vérification d'appartenance à la roue."""
        wheel = await self.wheel_repo.get(wheel_id)
        if not wheel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Roue {wheel_id} introuvable",
            )
        slot = await self.wheel_repo.get_slot(slot_id)
        if not slot or slot.wheel_id != wheel_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Slot {slot_id} introuvable sur la roue {wheel_id}",
            )
        return WheelSlotResponse.from_model(slot)

    async def update_slot(
        self,
        wheel_id: UUID,
        slot_id: UUID,
        data: WheelSlotUpdateRequest,
    ) -> WheelSlotResponse:
        """Met à jour le label d'un slot.

        Raises
        ------
        HTTPException 404 si roue ou slot non trouvé.

        """
        wheel = await self.wheel_repo.get(wheel_id)
        if not wheel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Roue {wheel_id} introuvable",
            )
        slot = await self.wheel_repo.get_slot(slot_id)
        if not slot or slot.wheel_id != wheel_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Slot {slot_id} introuvable sur la roue {wheel_id}",
            )
        slot.c_label = data.c_label
        updated = await self.wheel_repo.update_slot(slot)
        return WheelSlotResponse.from_model(updated)
