"""IoT Worker — enregistre les tâches Celery de la queue 'iot'."""

from medbox.iotworker.tasks import dispense  # noqa: F401
