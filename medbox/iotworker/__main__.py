"""Entrée CLI : démarre le Celery worker IoT + le listener MQTT en parallèle."""

from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
import threading

logger = logging.getLogger(__name__)


def _run_celery() -> None:
    """Lance le worker Celery sur la queue 'iot' (thread bloquant)."""
    proc = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "celery",
            "-A",
            "medbox.iotworker.broker",
            "worker",
            "--loglevel=info",
            "-Q",
            "iot",
            "-c",
            "4",
            "-n",
            "iot@%i",
        ],
        check=False,
    )
    if proc.returncode != 0:
        logger.error("Celery worker terminé avec code %s", proc.returncode)
        # Forcer l'arrêt du processus principal si Celery plante
        sys.exit(proc.returncode)


def run() -> None:
    """Démarre les deux composants de l'IoT Worker."""
    logging.basicConfig(level=logging.INFO)

    # Celery worker dans un thread daemon
    celery_thread = threading.Thread(target=_run_celery, daemon=True, name="celery-iot")
    celery_thread.start()
    logger.info("Celery IoT worker démarré (thread)")

    # MQTT listener dans le thread principal (asyncio)
    from medbox.iotworker.mqtt_listener import start as mqtt_start

    logger.info("Démarrage du listener MQTT...")
    asyncio.run(mqtt_start())


if __name__ == "__main__":
    run()
