"""Listener MQTT async — pont EMQX ↔ Celery pour l'IoT Worker.

Ce module se connecte à EMQX en mTLS et dispatch les messages entrants
sous forme de tâches Celery sur la queue 'iot'. Zéro logique métier ici.

Topics souscrits :
    medbox/box/+/telemetry   → handle_telemetry
    medbox/box/+/events      → handle_box_event
    medbox/box/+/ack         → handle_ack (log only pour l'instant)
"""

from __future__ import annotations

import json
import logging
import ssl
from pathlib import Path

import aiomqtt

from medbox.core.config.settings import settings

logger = logging.getLogger(__name__)

# Topics et tâches associées
_TOPIC_HANDLERS: dict[str, str] = {
    "telemetry": "medbox.iotworker.tasks.telemetry.handle_telemetry",
    "events": "medbox.iotworker.tasks.telemetry.handle_box_event",
}


def _box_uid_from_topic(topic: str) -> str | None:
    """Extrait le box_uid depuis un topic 'medbox/box/{uid}/...'."""
    parts = topic.split("/")
    if len(parts) >= 3 and parts[0] == "medbox" and parts[1] == "box":
        return parts[2]
    return None


def _segment_from_topic(topic: str) -> str | None:
    """Retourne le dernier segment du topic (telemetry, events, ack...)."""
    parts = topic.split("/")
    return parts[-1] if parts else None


def _build_tls_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context(
        ssl.Purpose.SERVER_AUTH, cafile=settings.emqx_ca_cert
    )
    ctx.load_cert_chain(
        certfile=settings.emqx_client_cert, keyfile=settings.emqx_client_key
    )
    return ctx


def _get_cert_cn() -> str:
    """Lit le CN du certificat client pour l'utiliser comme username MQTT."""
    from cryptography import x509

    with Path(settings.emqx_client_cert).open("rb") as f:
        cert = x509.load_pem_x509_certificate(f.read())

    cn = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
    return cn[0].value if cn else "medbox-iot-worker"


async def start() -> None:
    """Démarre le listener MQTT. Reconnexion automatique en cas de coupure."""
    from medbox.core.celery_app import celery_app

    tls_ctx = _build_tls_context()
    username = _get_cert_cn()

    logger.info(
        "Connexion EMQX %s:%s (mTLS cert=%s)",
        settings.emqx_host,
        settings.emqx_port,
        settings.emqx_client_cert,
    )

    async with aiomqtt.Client(
        hostname=settings.emqx_host,
        port=settings.emqx_port,
        tls_context=tls_ctx,
        username=username,
    ) as client:
        await client.subscribe("medbox/box/+/telemetry", qos=1)
        await client.subscribe("medbox/box/+/events", qos=1)
        await client.subscribe("medbox/box/+/ack", qos=1)

        logger.info("MQTT listener actif — en attente de messages")

        async for message in client.messages:
            topic = str(message.topic)
            segment = _segment_from_topic(topic)
            box_uid = _box_uid_from_topic(topic)

            if not box_uid:
                logger.warning("Topic inattendu ignoré : %s", topic)
                continue

            if segment == "ack":
                logger.debug("ACK reçu box=%s payload=%s", box_uid, message.payload)
                continue

            task_name = _TOPIC_HANDLERS.get(segment)
            if not task_name:
                logger.warning("Segment inconnu '%s' sur topic %s", segment, topic)
                continue

            try:
                payload = json.loads(message.payload)
            except json.JSONDecodeError:
                logger.error(
                    "Payload JSON invalide sur %s : %r", topic, message.payload
                )
                continue

            celery_app.send_task(task_name, args=[box_uid, payload])
            logger.debug("Tâche '%s' dispatchée pour box=%s", task_name, box_uid)
