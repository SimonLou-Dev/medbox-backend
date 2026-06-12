"""Types d'événements WebSocket."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class WsEvent(BaseModel):
    """Enveloppe d'un événement WebSocket."""

    type: str
    payload: dict[str, Any]
    timestamp: datetime = None

    def model_post_init(self, __context: Any) -> None:
        if self.timestamp is None:
            self.timestamp = datetime.now(tz=UTC)


# ---------------------------------------------------------------------------
# Helpers de construction d'événements
# ---------------------------------------------------------------------------


def action_success(message: str, data: dict | None = None) -> WsEvent:
    return WsEvent(type="ACTION_SUCCESS", payload={"message": message, **(data or {})})


def action_error(message: str, data: dict | None = None) -> WsEvent:
    return WsEvent(type="ACTION_ERROR", payload={"message": message, **(data or {})})


def box_alert(box_id: UUID, alert_type: str, detail: str) -> WsEvent:
    return WsEvent(
        type="BOX_ALERT",
        payload={"box_id": str(box_id), "alert_type": alert_type, "detail": detail},
    )


def take_event(box_uid: str, item_id: str, status: str) -> WsEvent:
    return WsEvent(
        type="TAKE_EVENT",
        payload={"box_uid": box_uid, "item_id": item_id, "status": status},
    )


def box_status_update(box_id: str, status: str, battery_level: float | None) -> WsEvent:
    return WsEvent(
        type="BOX_STATUS",
        payload={"box_id": box_id, "status": status, "battery_level": battery_level},
    )


def distribution_update(item_id: str, status: str, taken_at: str | None) -> WsEvent:
    return WsEvent(
        type="DISTRIBUTION_UPDATE",
        payload={"item_id": item_id, "status": status, "taken_at": taken_at},
    )
