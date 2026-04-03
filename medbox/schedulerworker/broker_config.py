"""Point d'entrée Celery pour le Scheduler Worker.

Le Scheduler Worker consomme la queue 'scheduler'.
Celery Beat tourne en parallèle pour déclencher les tâches périodiques.

Lancement worker  : celery -A medbox.schedulerworker.broker_config worker -Q scheduler -c 2
Lancement beat    : celery -A medbox.schedulerworker.broker_config beat --loglevel=info
"""

from medbox.core.celery_app import celery_app  # noqa: F401 — expose l'app Celery
