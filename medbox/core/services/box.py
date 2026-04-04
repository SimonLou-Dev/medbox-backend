"""Service de gestion des boîtiers physiques."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from medbox.core.db.models.box import Box
from medbox.core.db.repositories.box import BoxRepository
from medbox.core.db.repositories.telemetry import TelemetryRepository
from medbox.core.dto.box import (
    BoxRequest,
    BoxResponse,
    BoxStatsResponse,
    BoxStatusUpdateRequest,
)


class BoxService:
    """Service CRUD pour les Box, scoped par tenant."""

    def __init__(
        self,
        tenant_id: UUID,
        box_repo: BoxRepository | None = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.box_repo = box_repo or BoxRepository(tenant_id=tenant_id)

    async def get_stats(self) -> BoxStatsResponse:
        """Statistiques agrégées des boxes du tenant."""
        data = await self.box_repo.get_stats()
        return BoxStatsResponse(**data)

    async def get_telemetry(
        self, box_uid: str, metric: str | None = None, limit: int = 100
    ):
        """Retourne l'historique de télémétrie d'une box (vérification tenant)."""
        box = await self.box_repo.get_by_uid(box_uid)
        if not box or box.tenant_id != self.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Box '{box_uid}' introuvable",
            )
        return await TelemetryRepository().list_by_box(
            box.id, metric=metric, limit=limit
        )

    async def list_paginated(
        self, page: int = 1, per_page: int = 20
    ) -> tuple[int, list]:
        """Liste les boxes du tenant avec pagination."""
        return await self.box_repo.list_paginated(page=page, per_page=per_page)

    async def list(self) -> list[BoxResponse]:
        """Liste toutes les boxes du tenant."""
        boxes = await self.box_repo.list(with_relations=False)
        return [BoxResponse.from_model(b) for b in boxes]

    async def get(self, box_id: UUID) -> BoxResponse:
        """Récupère une box par ID.

        Raises
        ------
        HTTPException 404 si non trouvée.

        """
        box = await self.box_repo.get(box_id)
        if not box:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Box {box_id} introuvable",
            )
        return BoxResponse.from_model(box)

    async def create(self, data: BoxRequest) -> BoxResponse:
        """Crée une nouvelle box.

        Raises
        ------
        HTTPException 409 si box_uid déjà utilisé.

        """
        existing = await self.box_repo.get_by_uid(data.box_uid)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Une box avec le UID '{data.box_uid}' existe déjà",
            )

        box = Box(
            tenant_id=self.tenant_id,
            box_uid=data.box_uid,
            name=data.name,
            patient_id=data.patient_id,
            status=data.status,
            firmware_version=data.firmware_version,
            timezone=data.timezone,
        )
        created = await self.box_repo.create(box)
        return BoxResponse.from_model(created)

    async def update(self, box_id: UUID, data: BoxRequest) -> BoxResponse:
        """Met à jour une box existante.

        Raises
        ------
        HTTPException 404 si non trouvée.
        HTTPException 409 si box_uid déjà pris par une autre box.

        """
        box = await self.box_repo.get(box_id)
        if not box:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Box {box_id} introuvable",
            )

        if data.box_uid != box.box_uid:
            existing = await self.box_repo.get_by_uid(data.box_uid)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Une box avec le UID '{data.box_uid}' existe déjà",
                )

        box.box_uid = data.box_uid
        box.name = data.name
        box.patient_id = data.patient_id
        box.status = data.status
        box.firmware_version = data.firmware_version
        box.timezone = data.timezone

        updated = await self.box_repo.update(box)
        return BoxResponse.from_model(updated)

    async def update_status(
        self,
        box_id: UUID,
        data: BoxStatusUpdateRequest,
    ) -> BoxResponse:
        """Met à jour uniquement le statut d'une box."""
        box = await self.box_repo.get(box_id)
        if not box:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Box {box_id} introuvable",
            )
        box.status = data.status
        updated = await self.box_repo.update(box)
        return BoxResponse.from_model(updated)

    async def delete(self, box_id: UUID) -> bool:
        """Supprime une box.

        Raises
        ------
        HTTPException 404 si non trouvée.

        """
        box = await self.box_repo.get(box_id)
        if not box:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Box {box_id} introuvable",
            )
        return await self.box_repo.delete(box_id)
