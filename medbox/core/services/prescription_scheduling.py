"""Service de gestion des statuts de distribution."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from medbox.core.db.repositories.prescription_schedule_item import (
    PrescriptionScheduleItemRepository,
)
from medbox.core.dto.prescription_schedule_item import PrescriptionScheduleItemResponse


class PrescriptionSchedulingService:
    """Service pour mettre à jour les statuts des distributions.

    Les distributions sont créées exclusivement par WheelLoadPlanService.
    Ce service gère uniquement les transitions de statut déclenchées
    par la medbox via MQTT (taken, error).
    """

    def __init__(
        self,
        tenant_id: UUID,
        repo: PrescriptionScheduleItemRepository | None = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.repo = repo or PrescriptionScheduleItemRepository(tenant_id=tenant_id)

    async def list_by_plan(
        self,
        plan_id: UUID,
    ) -> list[PrescriptionScheduleItemResponse]:
        """Liste toutes les distributions d'un plan de chargement."""
        items = await self.repo.list_by_plan(plan_id)
        return [PrescriptionScheduleItemResponse.from_model(i) for i in items]

    async def list_upcoming_for_box(
        self,
        box_id: UUID,
        limit: int = 3,
    ) -> list[PrescriptionScheduleItemResponse]:
        """Retourne les N prochaines distributions d'une box."""
        items = await self.repo.list_upcoming_by_box(box_id, limit=limit)
        return [PrescriptionScheduleItemResponse.from_model(i) for i in items]

    async def mark_taken(
        self,
        item_id: UUID,
        taken_at=None,
    ) -> PrescriptionScheduleItemResponse:
        """Marque une distribution comme effectuée (confirmée par la medbox)."""
        from datetime import UTC, datetime

        item = await self.repo.update_status(
            item_id,
            "taken",
            taken_at=taken_at or datetime.now(tz=UTC),
        )
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Distribution {item_id} introuvable",
            )
        return PrescriptionScheduleItemResponse.from_model(item)

    async def mark_error(
        self,
        item_id: UUID,
        reason: str,
    ) -> PrescriptionScheduleItemResponse:
        """Marque une distribution en erreur (ex: roue bloquée)."""
        item = await self.repo.update_status(item_id, "error", error_reason=reason)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Distribution {item_id} introuvable",
            )
        return PrescriptionScheduleItemResponse.from_model(item)
