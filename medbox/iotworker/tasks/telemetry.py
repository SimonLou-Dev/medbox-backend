"""Tâches Celery IoT Worker — traitement télémétrie et événements box."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from medbox.core.celery_app import celery_app

if TYPE_CHECKING:
    from datetime import datetime

    from medbox.core.db.models.box import Box

logger = logging.getLogger(__name__)

RTC_DRIFT_THRESHOLD_SECONDS = 600  # 10 minutes


async def _send_rtc_sync(box_uid: str, server_time_iso: str) -> None:
    """Publie une commande sync_time vers la box via MQTT."""
    import json
    import ssl

    import aiomqtt

    from medbox.core.config.settings import settings

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
            f"medbox/box/{box_uid}/cmd/sync_time",
            payload=json.dumps({"server_time": server_time_iso}),
            qos=1,
        )


async def _check_rtc_drift(
    box_uid: str,
    box: Box,
    payload: dict,
    now: datetime,
) -> tuple[float | None, bool]:
    """Calculate RTC drift, store it, and send a correction command if needed."""
    from datetime import datetime

    from medbox.core.db.models.telemetry import Telemetry
    from medbox.core.db.repositories.telemetry import TelemetryRepository

    if "current_date" not in payload:
        return None, False

    try:
        box_time = datetime.fromisoformat(
            payload["current_date"].replace("Z", "+00:00"),
        )
    except (ValueError, AttributeError) as e:
        logger.warning("current_date invalide pour box %s : %s", box_uid, e)
        return None, False

    drift_seconds = abs((now - box_time).total_seconds())

    await TelemetryRepository().add(
        Telemetry(
            tenant_id=box.tenant_id,
            box_id=box.id,
            metric="rtc_drift_seconds",
            value_number=drift_seconds,
        )
    )

    if drift_seconds <= RTC_DRIFT_THRESHOLD_SECONDS:
        return drift_seconds, False

    logger.warning(
        "Dérive RTC box=%s : %.0fs — envoi sync_time",
        box_uid,
        drift_seconds,
    )
    await _send_rtc_sync(box_uid, now.isoformat())
    return drift_seconds, True


@celery_app.task(
    name="medbox.iotworker.tasks.telemetry.handle_telemetry",
    queue="iot",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def handle_telemetry(self, box_uid: str, payload: dict) -> dict:
    """Handle telemetry frame received from a box via MQTT.

    Updates last_seen_at, firmware_version and last_sync_at on the Box.
    If RTC drift exceeds 10 minutes, publishes a sync_time command.

    Payload:
        {
            "firmware_version": "1.2.3",
            "last_sync": "2026-04-03T08:00:00Z",
            "current_date": "2026-04-03T09:45:00Z"
        }
    """

    async def _run() -> dict:
        from datetime import UTC, datetime

        from sqlalchemy import select

        from medbox.core.db.models.box import Box
        from medbox.core.db.session import async_session_local

        now = datetime.now(tz=UTC)

        async with async_session_local() as session:
            result = await session.execute(select(Box).where(Box.box_uid == box_uid))
            box = result.scalar_one_or_none()

        if not box:
            logger.warning("handle_telemetry: box UID %s introuvable", box_uid)
            return {"status": "skipped", "reason": "box_not_found"}

        box_updates: dict = {"last_seen_at": now}
        if "firmware_version" in payload:
            box_updates["firmware_version"] = str(payload["firmware_version"])
        if "last_sync" in payload:
            try:
                box_updates["last_sync_at"] = datetime.fromisoformat(
                    payload["last_sync"].replace("Z", "+00:00"),
                )
            except (ValueError, AttributeError):
                logger.warning(
                    "last_sync invalide pour box %s : %s",
                    box_uid,
                    payload["last_sync"],
                )

        # Infos reseau remontees par le firmware (cle courte ou longue)
        mac = payload.get("mac") or payload.get("mac_address")
        if mac:
            box_updates["mac_address"] = str(mac)
        ip = payload.get("ip") or payload.get("ip_address")
        if ip:
            box_updates["ip_address"] = str(ip)

        async with async_session_local() as session:
            result = await session.execute(select(Box).where(Box.box_uid == box_uid))
            box = result.scalar_one_or_none()
            if box:
                for k, v in box_updates.items():
                    setattr(box, k, v)
                await session.commit()

        drift_seconds, rtc_correction_sent = await _check_rtc_drift(
            box_uid,
            box,
            payload,
            now,
        )

        # Notifier le front — box vue en ligne
        try:
            from medbox.api.ws.events import box_status_update
            from medbox.api.ws.manager import publish_to_tenant

            await publish_to_tenant(
                str(box.tenant_id),
                box_status_update(str(box.id), box.status, None),
            )
        except Exception as ws_exc:
            logger.debug("WS publish failed (non-blocking) : %s", ws_exc)

        logger.info(
            "Télémétrie reçue box=%s drift=%.0fs correction=%s",
            box_uid,
            drift_seconds or 0,
            rtc_correction_sent,
        )
        return {
            "status": "ok",
            "box_uid": box_uid,
            "drift_seconds": drift_seconds,
            "rtc_correction_sent": rtc_correction_sent,
        }

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("Erreur handle_telemetry box=%s : %s", box_uid, exc)
        raise self.retry(exc=exc) from exc


@celery_app.task(
    name="medbox.iotworker.tasks.telemetry.handle_box_event",
    queue="iot",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def handle_box_event(self, box_uid: str, payload: dict) -> dict:
    """Handle an event received from a box via MQTT.

    Updates last_seen_at on the Box and creates an Event record.

    Payload:
        {"type": "DISTRIBUTION_OK", "schedule_item_id": "uuid", "slot_index": 2}
    """

    async def _run() -> dict:
        from datetime import UTC, datetime

        from sqlalchemy import select

        from medbox.core.db.models.box import Box
        from medbox.core.db.models.event import Event
        from medbox.core.db.repositories.event import EventRepository
        from medbox.core.db.session import async_session_local

        event_type = payload.get("type", "UNKNOWN")

        async with async_session_local() as session:
            result = await session.execute(select(Box).where(Box.box_uid == box_uid))
            box = result.scalar_one_or_none()

        if not box:
            logger.warning("handle_box_event: box UID %s introuvable", box_uid)
            return {"status": "skipped", "reason": "box_not_found"}

        async with async_session_local() as session:
            result = await session.execute(select(Box).where(Box.box_uid == box_uid))
            box = result.scalar_one_or_none()
            if box:
                box.last_seen_at = datetime.now(tz=UTC)
                await session.commit()

        await EventRepository().add(
            Event(
                tenant_id=box.tenant_id,
                box_id=box.id,
                type=event_type,
                payload={k: v for k, v in payload.items() if k != "type"},
            )
        )

        logger.info("Événement reçu box=%s type=%s", box_uid, event_type)
        return {"status": "ok", "box_uid": box_uid, "event_type": event_type}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("Erreur handle_box_event box=%s : %s", box_uid, exc)
        raise self.retry(exc=exc) from exc
