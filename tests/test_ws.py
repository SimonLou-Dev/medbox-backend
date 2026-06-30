"""Tests — ConnectionManager WebSocket, événements, endpoint auth."""

import contextlib
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect, WebSocketState

from medbox.api.ws.events import (
    action_error,
    action_success,
    box_alert,
    box_status_update,
    distribution_update,
    take_event,
)
from medbox.api.ws.manager import ConnectionManager
from medbox.core.services.security import SecurityService

_TENANT_ID = str(uuid4())
_USER_ID = str(uuid4())
_VALID_CLAIMS = {"sub": _USER_ID, "tenant_id": _TENANT_ID}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ws_app():
    """App FastAPI minimale sans middlewares pour tester les endpoints WS."""
    from fastapi import FastAPI

    from medbox.api.routes.v1.ws import router

    a = FastAPI()
    a.include_router(router, prefix="/api/v1")
    return a


def _valid_auth():
    return patch.object(SecurityService, "decode_token", new=AsyncMock(return_value=_VALID_CLAIMS))


def _invalid_auth():
    return patch.object(
        SecurityService, "decode_token", new=AsyncMock(side_effect=Exception("bad token"))
    )


def _noop_redis():
    async def _fake(*_args, **_kwargs):
        import asyncio

        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.sleep(100)

    return patch("medbox.api.routes.v1.ws.redis_listener", new=_fake)


# ===========================================================================
# ConnectionManager
# ===========================================================================


class TestConnectionManager:
    def test_connect_increments_count(self):
        mgr = ConnectionManager()
        mgr.connect("t1", "u1", MagicMock())
        assert mgr.connection_count() == 1

    def test_disconnect_decrements_count(self):
        mgr = ConnectionManager()
        ws = MagicMock()
        mgr.connect("t1", "u1", ws)
        mgr.disconnect("t1", "u1", ws)
        assert mgr.connection_count() == 0

    def test_disconnect_removes_empty_tenant(self):
        mgr = ConnectionManager()
        ws = MagicMock()
        mgr.connect("t1", "u1", ws)
        mgr.disconnect("t1", "u1", ws)
        assert "t1" not in mgr._connections

    def test_multiple_users_same_tenant(self):
        mgr = ConnectionManager()
        mgr.connect("t1", "u1", MagicMock())
        mgr.connect("t1", "u2", MagicMock())
        assert mgr.connection_count() == 2

    def test_same_user_multiple_connections(self):
        mgr = ConnectionManager()
        mgr.connect("t1", "u1", MagicMock())
        mgr.connect("t1", "u1", MagicMock())
        assert mgr.connection_count() == 2

    async def test_notify_user_targets_correct_user(self):
        mgr = ConnectionManager()
        ws_target = MagicMock()
        ws_target.client_state = WebSocketState.CONNECTED
        ws_target.send_text = AsyncMock()
        ws_other = MagicMock()
        ws_other.client_state = WebSocketState.CONNECTED
        ws_other.send_text = AsyncMock()

        mgr.connect("t1", "u1", ws_target)
        mgr.connect("t1", "u2", ws_other)

        await mgr.notify_user("t1", "u1", action_success("ping"))

        ws_target.send_text.assert_awaited_once()
        ws_other.send_text.assert_not_awaited()

    async def test_broadcast_reaches_all_users(self):
        mgr = ConnectionManager()
        ws1 = MagicMock()
        ws1.client_state = WebSocketState.CONNECTED
        ws1.send_text = AsyncMock()
        ws2 = MagicMock()
        ws2.client_state = WebSocketState.CONNECTED
        ws2.send_text = AsyncMock()

        mgr.connect("t1", "u1", ws1)
        mgr.connect("t1", "u2", ws2)

        await mgr.broadcast_tenant("t1", action_success("all"))

        ws1.send_text.assert_awaited_once()
        ws2.send_text.assert_awaited_once()

    async def test_tenant_isolation_broadcast(self):
        mgr = ConnectionManager()
        ws_a = MagicMock()
        ws_a.client_state = WebSocketState.CONNECTED
        ws_a.send_text = AsyncMock()
        ws_b = MagicMock()
        ws_b.client_state = WebSocketState.CONNECTED
        ws_b.send_text = AsyncMock()

        mgr.connect("tenant-a", "u1", ws_a)
        mgr.connect("tenant-b", "u2", ws_b)

        await mgr.broadcast_tenant("tenant-a", action_success("a only"))

        ws_a.send_text.assert_awaited_once()
        ws_b.send_text.assert_not_awaited()

    async def test_disconnected_ws_skipped(self):
        mgr = ConnectionManager()
        ws = MagicMock()
        ws.client_state = WebSocketState.DISCONNECTED
        ws.send_text = AsyncMock()

        mgr.connect("t1", "u1", ws)
        await mgr.notify_user("t1", "u1", action_success("test"))

        ws.send_text.assert_not_awaited()

    async def test_send_error_handled_silently(self):
        mgr = ConnectionManager()
        ws = MagicMock()
        ws.client_state = WebSocketState.CONNECTED
        ws.send_text = AsyncMock(side_effect=RuntimeError("broken pipe"))

        mgr.connect("t1", "u1", ws)
        # Must not raise
        await mgr.notify_user("t1", "u1", action_success("test"))


# ===========================================================================
# WsEvent
# ===========================================================================


class TestWsEvents:
    def test_action_success_type_and_payload(self):
        e = action_success("done", {"key": "val"})
        assert e.type == "ACTION_SUCCESS"
        assert e.payload["message"] == "done"
        assert e.payload["key"] == "val"

    def test_action_error_type(self):
        e = action_error("oops")
        assert e.type == "ACTION_ERROR"
        assert e.payload["message"] == "oops"

    def test_box_alert_payload(self):
        bid = uuid4()
        e = box_alert(bid, "battery_low", "5%")
        assert e.type == "BOX_ALERT"
        assert e.payload["box_id"] == str(bid)
        assert e.payload["alert_type"] == "battery_low"

    def test_take_event_payload(self):
        e = take_event("BOX-001", "item-abc", "taken")
        assert e.type == "TAKE_EVENT"
        assert e.payload["box_uid"] == "BOX-001"
        assert e.payload["status"] == "taken"

    def test_box_status_update(self):
        e = box_status_update("box-1", "active", 85.0)
        assert e.type == "BOX_STATUS"
        assert e.payload["status"] == "active"
        assert e.payload["battery_level"] == 85.0

    def test_distribution_update(self):
        e = distribution_update("item-1", "taken", "2026-06-12T08:00:00Z")
        assert e.type == "DISTRIBUTION_UPDATE"
        assert e.payload["status"] == "taken"

    def test_event_json_serializable(self):
        e = action_success("test")
        data = json.loads(e.model_dump_json())
        assert data["type"] == "ACTION_SUCCESS"
        assert "timestamp" in data

    def test_timestamp_auto_set(self):
        e = action_success("x")
        assert e.timestamp is not None


# ===========================================================================
# WS endpoint — authentification et ping/pong
# ===========================================================================


class TestWsEndpointAuth:
    def test_invalid_token_closes_with_4001(self):
        client = TestClient(_make_ws_app(), raise_server_exceptions=False)
        url = "/api/v1/ws/notifications?token=bad"
        with (
            _invalid_auth(),
            pytest.raises(WebSocketDisconnect) as exc_info,
            client.websocket_connect(url) as ws,
        ):
            ws.receive_text()
        assert exc_info.value.code == 4001

    def test_missing_tenant_closes_with_4001(self):
        client = TestClient(_make_ws_app(), raise_server_exceptions=False)
        no_tenant = {"sub": str(uuid4())}
        url = "/api/v1/ws/notifications?token=tok"
        with (
            patch.object(SecurityService, "decode_token", new=AsyncMock(return_value=no_tenant)),
            pytest.raises(WebSocketDisconnect) as exc_info,
            client.websocket_connect(url) as ws,
        ):
            ws.receive_text()
        assert exc_info.value.code == 4001

    def test_missing_user_closes_with_4001(self):
        client = TestClient(_make_ws_app(), raise_server_exceptions=False)
        no_sub = {"tenant_id": str(uuid4())}
        url = "/api/v1/ws/notifications?token=tok"
        with (
            patch.object(SecurityService, "decode_token", new=AsyncMock(return_value=no_sub)),
            pytest.raises(WebSocketDisconnect) as exc_info,
            client.websocket_connect(url) as ws,
        ):
            ws.receive_text()
        assert exc_info.value.code == 4001

    def test_valid_token_ping_pong(self):
        client = TestClient(_make_ws_app(), raise_server_exceptions=False)
        with _valid_auth(), _noop_redis(), client.websocket_connect("/api/v1/ws/notifications?token=valid") as ws:
            ws.send_text('{"type":"ping"}')
            response = ws.receive_text()
        assert json.loads(response)["type"] == "pong"

    def test_live_endpoint_invalid_token(self):
        client = TestClient(_make_ws_app(), raise_server_exceptions=False)
        with (
            _invalid_auth(),
            pytest.raises(WebSocketDisconnect) as exc_info,
            client.websocket_connect("/api/v1/ws/live?token=bad") as ws,
        ):
            ws.receive_text()
        assert exc_info.value.code == 4001

    def test_live_endpoint_valid_token_ping_pong(self):
        client = TestClient(_make_ws_app(), raise_server_exceptions=False)
        with _valid_auth(), _noop_redis(), client.websocket_connect("/api/v1/ws/live?token=valid") as ws:
            ws.send_text('{"type":"ping"}')
            response = ws.receive_text()
        assert json.loads(response)["type"] == "pong"

