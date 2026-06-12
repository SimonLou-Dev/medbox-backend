"""Connection Manager WebSocket.

Gère les connexions actives et la diffusion d'événements via Redis pub/sub.

Architecture :
- In-memory : registre des WebSocket actives par tenant/user (dans ce process API)
- Redis pub/sub : canal de communication entre workers (IoT, Scheduler) et l'API
  - Workers publient sur `ws:tenant:{tenant_id}` ou `ws:user:{user_id}`
  - Chaque connexion WS écoute son canal Redis et forward au client
"""

from __future__ import annotations

import logging
from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from medbox.api.ws.events import WsEvent
from medbox.core.config.settings import settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Registre des connexions WebSocket actives.

    Thread-safety : FastAPI tourne dans un event loop unique (asyncio),
    les opérations sur les dicts sont donc safe sans lock.
    """

    def __init__(self) -> None:
        # tenant_id (str) → user_id (str) → list[WebSocket]
        self._connections: dict[str, dict[str, list[WebSocket]]] = defaultdict(
            lambda: defaultdict(list)
        )

    def connect(self, tenant_id: str, user_id: str, ws: WebSocket) -> None:
        self._connections[tenant_id][user_id].append(ws)
        logger.debug("WS connect : tenant=%s user=%s", tenant_id, user_id)

    def disconnect(self, tenant_id: str, user_id: str, ws: WebSocket) -> None:
        conns = self._connections[tenant_id][user_id]
        conns.remove(ws)
        if not conns:
            del self._connections[tenant_id][user_id]
        if not self._connections[tenant_id]:
            del self._connections[tenant_id]
        logger.debug("WS disconnect : tenant=%s user=%s", tenant_id, user_id)

    async def notify_user(self, tenant_id: str, user_id: str, event: WsEvent) -> None:
        """Envoie un événement à toutes les connexions d'un utilisateur."""
        sockets = self._connections.get(tenant_id, {}).get(user_id, [])
        data = event.model_dump_json()
        for ws in list(sockets):
            await _safe_send(ws, data)

    async def broadcast_tenant(self, tenant_id: str, event: WsEvent) -> None:
        """Diffuse un événement à tous les utilisateurs connectés d'un tenant."""
        data = event.model_dump_json()
        for sockets in self._connections.get(tenant_id, {}).values():
            for ws in list(sockets):
                await _safe_send(ws, data)

    def connection_count(self) -> int:
        return sum(
            len(ws_list)
            for users in self._connections.values()
            for ws_list in users.values()
        )


async def _safe_send(ws: WebSocket, data: str) -> None:
    """Envoie sans lever d'exception si la connexion est fermée."""
    try:
        if ws.client_state == WebSocketState.CONNECTED:
            await ws.send_text(data)
    except Exception as exc:
        logger.debug("WS send failed : %s", exc)


# Instance globale (singleton dans le process API)
manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Redis pub/sub — publication depuis les workers
# ---------------------------------------------------------------------------


async def publish_to_tenant(tenant_id: str | UUID, event: WsEvent) -> None:
    """Publie un événement sur le canal Redis d'un tenant.

    Appelé depuis les workers Celery pour notifier le process API.
    """
    import redis.asyncio as aioredis

    channel = f"ws:tenant:{tenant_id}"
    data = event.model_dump_json()
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await r.publish(channel, data)
    finally:
        await r.aclose()


async def publish_to_user(
    tenant_id: str | UUID, user_id: str | UUID, event: WsEvent
) -> None:
    """Publie un événement sur le canal Redis d'un utilisateur spécifique."""
    import redis.asyncio as aioredis

    channel = f"ws:user:{tenant_id}:{user_id}"
    data = event.model_dump_json()
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await r.publish(channel, data)
    finally:
        await r.aclose()


async def redis_listener(tenant_id: str, user_id: str, ws: WebSocket) -> None:
    """Écoute les canaux Redis du tenant/user et forward les messages au client WS.

    Tourne en arrière-plan pendant toute la durée de la connexion WS.
    """
    import redis.asyncio as aioredis

    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()

    tenant_channel = f"ws:tenant:{tenant_id}"
    user_channel = f"ws:user:{tenant_id}:{user_id}"

    await pubsub.subscribe(tenant_channel, user_channel)
    logger.debug("Redis listener démarré : %s / %s", tenant_channel, user_channel)

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            if ws.client_state != WebSocketState.CONNECTED:
                break
            await _safe_send(ws, message["data"])
    except Exception as exc:
        logger.debug("Redis listener terminé : %s", exc)
    finally:
        await pubsub.unsubscribe(tenant_channel, user_channel)
        await r.aclose()
