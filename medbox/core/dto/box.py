"""DTOs pour les boîtiers physiques."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from medbox.core.config.settings import settings
from medbox.core.db.models.box import Box


def compute_connection_status(
    last_seen_at: datetime | None,
    admin_status: str | None = None,
) -> str:
    """Calcule l'etat de connexion reel d'une box.

    Retours possibles :
      - "never_connected" : aucune telemetry jamais recue
      - "online"          : telemetry recue dans les N dernieres minutes
      - "offline"         : telemetry plus ancienne que le seuil
      - "inactive"        : admin_status == "inactive" (box non adoptee / desactivee)
      - "maintenance"     : admin_status == "maintenance" (erreur materielle)

    Le seuil N est configurable via BOX_OFFLINE_THRESHOLD_MINUTES (defaut 10).
    """
    # Statuts administratifs explicites prevalent sur la connectivite
    if admin_status in ("inactive", "maintenance", "error"):
        return admin_status
    if last_seen_at is None:
        return "never_connected"
    # Normaliser le fuseau si naif
    if last_seen_at.tzinfo is None:
        last_seen_at = last_seen_at.replace(tzinfo=UTC)
    threshold = datetime.now(tz=UTC) - timedelta(
        minutes=settings.box_offline_threshold_minutes
    )
    return "online" if last_seen_at >= threshold else "offline"


class BoxRequest(BaseModel):
    """Données pour créer ou mettre à jour une box."""

    box_uid: str
    name: str | None = None
    patient_id: UUID | None = None
    status: str = "active"
    firmware_version: str | None = None
    timezone: str | None = None


class BoxResponse(BaseModel):
    """Réponse représentant une box."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(exclude=True)  # interne uniquement, non exposé en JSON
    box_uid: str
    tenant_id: UUID | None
    name: str | None
    patient_id: UUID | None
    status: str  # statut administratif : active|inactive|maintenance|error
    connection_status: str = Field(
        default="never_connected",
        description=(
            "Etat de connexion calcule depuis last_seen_at : "
            "online|offline|never_connected|inactive|maintenance"
        ),
    )
    firmware_version: str | None
    timezone: str | None
    last_seen_at: datetime | None
    last_sync_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, box: Box) -> BoxResponse:
        instance = cls.model_validate(box)
        instance.connection_status = compute_connection_status(
            box.last_seen_at, box.status
        )
        return instance


class BoxStatusUpdateRequest(BaseModel):
    """Mise à jour du statut d'une box."""

    status: str


class BoxStatsResponse(BaseModel):
    """Statistiques agrégées des boxes du tenant."""

    total: int
    online: int  # last_seen_at < seuil
    offline_alert: int  # actives mais non vues depuis > seuil
    never_connected: int  # jamais vues (last_seen_at is null) et actives
