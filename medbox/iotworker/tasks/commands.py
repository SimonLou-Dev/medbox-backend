"""Tâches d'envoi de commandes MQTT vers les boxes."""

from __future__ import annotations

import asyncio
import json
import logging
import ssl

from medbox.core.celery_app import celery_app
from medbox.core.config.settings import settings

logger = logging.getLogger(__name__)


async def _publish_command(box_uid: str, command: str, payload: dict) -> None:
    """Publie une commande sur medbox/box/{box_uid}/cmd/{command}."""
    import aiomqtt

    tls_ctx = ssl.create_default_context(
        ssl.Purpose.SERVER_AUTH,
        cafile=settings.emqx_ca_cert,
    )
    tls_ctx.load_cert_chain(
        certfile=settings.emqx_client_cert,
        keyfile=settings.emqx_client_key,
    )
    async with aiomqtt.Client(
        hostname=settings.emqx_host,
        port=settings.emqx_port,
        tls_context=tls_ctx,
        username="medbox-iot-worker",
    ) as mqtt:
        await mqtt.publish(
            f"medbox/box/{box_uid}/cmd/{command}",
            payload=json.dumps(payload),
            qos=1,
        )


@celery_app.task(
    name="medbox.iotworker.tasks.commands.send_test_distribution",
    queue="iot",
)
def send_test_distribution(box_uid: str, days: int = 7) -> dict:
    """Publie une commande test_distribution vers une box (test moteur sur N jours)."""
    try:
        asyncio.run(_publish_command(box_uid, "test_distribution", {"days": days}))
        logger.info("test_distribution envoyé à box=%s (days=%d)", box_uid, days)
        return {"status": "ok", "box_uid": box_uid, "days": days}
    except Exception as exc:
        logger.error("Erreur send_test_distribution box=%s : %s", box_uid, exc)
        raise
