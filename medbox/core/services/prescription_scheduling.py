"""Service de planification des prises de médicaments."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status

from medbox.core.db.models.prescription_schedule_item import PrescriptionScheduleItem
from medbox.core.db.repositories.prescription_schedule_item import (
    PrescriptionScheduleItemRepository,
)
from medbox.core.dto.prescription_schedule_item import (
    PrescriptionScheduleItemRequest,
    PrescriptionScheduleItemResponse,
)


class PrescriptionSchedulingService:
    """Service pour créer et gérer les items de planning de prises.

    Utilisé par :
    - Le scheduler worker pour calculer et déclencher les prises
    - L'IoT worker pour marquer les prises comme taken/error
    """

    def __init__(
        self,
        tenant_id: UUID,
        repo: PrescriptionScheduleItemRepository | None = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.repo = repo or PrescriptionScheduleItemRepository(tenant_id=tenant_id)

    async def schedule(
        self,
        data: PrescriptionScheduleItemRequest,
    ) -> PrescriptionScheduleItemResponse:
        """Crée un item de planning pour une prise future."""
        item = PrescriptionScheduleItem(
            tenant_id=self.tenant_id,
            prescription_id=data.prescription_id,
            prescription_item_id=data.prescription_item_id,
            box_id=data.box_id,
            scheduled_at=data.scheduled_at,
            status="pending",
        )
        created = await self.repo.create(item)
        return PrescriptionScheduleItemResponse.from_model(created)

    async def get_due_items(
        self,
        now: datetime | None = None,
    ) -> list[PrescriptionScheduleItemResponse]:
        """Retourne les items dont l'heure de prise est dépassée (pending)."""
        items = await self.repo.list_due(now=now)
        return [PrescriptionScheduleItemResponse.from_model(i) for i in items]

    async def list_by_prescription(
        self,
        prescription_id: UUID,
    ) -> list[PrescriptionScheduleItemResponse]:
        """Liste tous les items planifiés d'une prescription."""
        items = await self.repo.list_by_prescription(prescription_id)
        return [PrescriptionScheduleItemResponse.from_model(i) for i in items]

    async def mark_dispatched(
        self,
        item_id: UUID,
    ) -> PrescriptionScheduleItemResponse:
        """Marque un item comme dispatché (commande envoyée à la box)."""
        item = await self.repo.update_status(
            item_id,
            "dispatched",
            dispatched_at=datetime.now(tz=UTC),
        )
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item de planning {item_id} introuvable",
            )
        return PrescriptionScheduleItemResponse.from_model(item)

    async def mark_taken(
        self,
        item_id: UUID,
    ) -> PrescriptionScheduleItemResponse:
        """Marque un item comme pris (confirmé par la box via MQTT)."""
        item = await self.repo.update_status(
            item_id,
            "taken",
            taken_at=datetime.now(tz=UTC),
        )
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item de planning {item_id} introuvable",
            )
        return PrescriptionScheduleItemResponse.from_model(item)

    async def mark_missed(
        self,
        item_id: UUID,
    ) -> PrescriptionScheduleItemResponse:
        """Marque un item comme manqué (délai dépassé sans confirmation)."""
        item = await self.repo.update_status(item_id, "missed")
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item de planning {item_id} introuvable",
            )
        return PrescriptionScheduleItemResponse.from_model(item)

    async def mark_error(
        self,
        item_id: UUID,
        reason: str,
    ) -> PrescriptionScheduleItemResponse:
        """Marque un item en erreur (ex: roue bloquée, timeout)."""
        item = await self.repo.update_status(item_id, "error", error_reason=reason)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item de planning {item_id} introuvable",
            )
        return PrescriptionScheduleItemResponse.from_model(item)
