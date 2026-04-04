"""DTOs pour la télémétrie."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from medbox.core.db.models.telemetry import Telemetry


class TelemetryResponse(BaseModel):
    """Entrée de télémétrie."""

    model_config = ConfigDict(from_attributes=True)

    metric: str
    value_number: float | None
    value_json: dict | None
    created_at: datetime

    @classmethod
    def from_model(cls, t: Telemetry) -> TelemetryResponse:
        return cls.model_validate(t)
