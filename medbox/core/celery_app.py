"""Application Celery centrale — partagée par tous les workers."""

from celery import Celery
from celery.schedules import crontab

from medbox.core.config.settings import settings

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

celery_app = Celery("medbox")

celery_app.config_from_object(
    {
        # Broker + backend Redis
        "broker_url": settings.redis_url,
        "result_backend": settings.redis_url,
        # Sérialisation
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        # Timezone
        "timezone": "UTC",
        "enable_utc": True,
        # Routage par queue
        # Les workers démarrent avec `-Q iot` ou `-Q scheduler`
        # pour ne consommer que leurs propres tâches.
        "task_routes": {
            "medbox.iotworker.tasks.*": {"queue": "iot"},
            "medbox.schedulerworker.tasks.*": {"queue": "scheduler"},
            "medbox.core.tasks.*": {"queue": "default"},
        },
        # Fiabilité
        "task_acks_late": True,
        "task_reject_on_worker_lost": True,
        "worker_prefetch_multiplier": 1,
        # Tâches périodiques (Celery Beat — lancé dans le scheduler worker)
        "beat_schedule": {
            # Dispatch des prises dues toutes les 5 minutes
            "dispatch-scheduled-takes": {
                "task": "medbox.schedulerworker.tasks.scheduling.dispatch_scheduled_takes",
                "schedule": 300,
                "options": {"queue": "scheduler"},
            },
            # Calcul des prochaines prises toutes les heures
            "calculate-prescription-scheduling": {
                "task": "medbox.schedulerworker.tasks.scheduling.calculate_prescription_scheduling",
                "schedule": 3600,
                "options": {"queue": "scheduler"},
            },
            # Surveillance des boxes toutes les 5 minutes
            "monitor-boxes": {
                "task": "medbox.schedulerworker.tasks.monitoring.monitor_boxes",
                "schedule": 300,
                "options": {"queue": "scheduler"},
            },
            # Nettoyage quotidien à 02:00 UTC
            "daily-cleanup": {
                "task": "medbox.schedulerworker.tasks.cleanup.cleanup_job",
                "schedule": crontab(hour=2, minute=0),
                "options": {"queue": "scheduler"},
            },
            # Sync médicaments BDPM quotidien à 03:00 UTC
            "medication-sync": {
                "task": "medbox.core.tasks.medication_sync.sync_medications_from_api",
                "schedule": crontab(hour=3, minute=0),
                "options": {"queue": "default"},
            },
        },
        # Autodiscovery des modules de tâches
        "imports": [
            "medbox.core.tasks.invitation_tasks",
            "medbox.core.tasks.medication_sync",
            "medbox.iotworker.tasks.dispense",
            "medbox.schedulerworker.tasks.scheduling",
            "medbox.schedulerworker.tasks.monitoring",
            "medbox.schedulerworker.tasks.cleanup",
        ],
    }
)
