"""Endpoints WebSocket — notifications et live updates."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from medbox.api.ws.manager import manager, redis_listener
from medbox.core.services.security import SecurityService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


async def _authenticate_ws(websocket: WebSocket, token: str) -> tuple[str, str] | None:
    """Valide le JWT et retourne (tenant_id, user_id) ou ferme la connexion."""
    svc = SecurityService()
    try:
        claims = await svc.decode_token(token)
        tenant_id = claims.get("tenant_id") or claims.get("tenantId")
        user_id = claims.get("sub")
        if not tenant_id or not user_id:
            await websocket.close(code=4001, reason="missing_tenant_or_user")
            return None
        return str(tenant_id), str(user_id)
    except Exception:
        await websocket.close(code=4001, reason="invalid_token")
        return None


@router.websocket("/ws/notifications")
async def ws_notifications(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
) -> None:
    """Canal de notifications UX en temps réel.

    Reçoit les événements : ACTION_SUCCESS, ACTION_ERROR, BOX_ALERT, TAKE_EVENT.

    Connexion : ws://api/v1/ws/notifications?token=<jwt>
    """
    await websocket.accept()

    result = await _authenticate_ws(websocket, token)
    if not result:
        return
    tenant_id, user_id = result

    manager.connect(tenant_id, user_id, websocket)
    logger.info(
        "WS notifications connecté : tenant=%s user=%s total=%d",
        tenant_id,
        user_id,
        manager.connection_count(),
    )

    # Listener Redis en arrière-plan (événements des workers)
    redis_task = asyncio.create_task(redis_listener(tenant_id, user_id, websocket))

    try:
        # Boucle principale : on reste connecté, on gère le ping/pong et les
        # messages entrants (le client peut envoyer {"type": "ping"})
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if data == '{"type":"ping"}' or data == "ping":
                    await websocket.send_text('{"type":"pong"}')
            except TimeoutError:
                # Heartbeat server-side
                await websocket.send_text('{"type":"ping"}')
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("WS notifications erreur : %s", exc)
    finally:
        redis_task.cancel()
        manager.disconnect(tenant_id, user_id, websocket)
        logger.info(
            "WS notifications déconnecté : tenant=%s user=%s total=%d",
            tenant_id,
            user_id,
            manager.connection_count(),
        )


@router.websocket("/ws/live")
async def ws_live(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
    box_id: str | None = Query(default=None, description="Filtrer par box_id"),
) -> None:
    """Canal live updates dashboard (état boxes, distributions).

    Reçoit les événements : BOX_STATUS, DISTRIBUTION_UPDATE.

    Connexion : ws://api/v1/ws/live?token=<jwt>&box_id=<uuid>
    """
    await websocket.accept()

    result = await _authenticate_ws(websocket, token)
    if not result:
        return
    tenant_id, user_id = result

    manager.connect(tenant_id, user_id, websocket)

    redis_task = asyncio.create_task(redis_listener(tenant_id, user_id, websocket))

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if data == '{"type":"ping"}' or data == "ping":
                    await websocket.send_text('{"type":"pong"}')
            except TimeoutError:
                await websocket.send_text('{"type":"ping"}')
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("WS live erreur : %s", exc)
    finally:
        redis_task.cancel()
        manager.disconnect(tenant_id, user_id, websocket)
