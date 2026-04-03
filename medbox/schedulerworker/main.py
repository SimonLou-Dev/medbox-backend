"""Scheduler Worker — enregistre les tâches Celery de la queue 'scheduler'."""

from medbox.schedulerworker.tasks import cleanup, monitoring, scheduling  # noqa: F401
