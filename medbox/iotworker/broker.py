"""Point d'entrée Celery pour l'IoT Worker.

L'IoT Worker consomme exclusivement la queue 'iot'.
Lancement : celery -A medbox.iotworker.broker worker -Q iot -c 4
"""

from medbox.core.celery_app import celery_app  # noqa: F401 — expose l'app Celery
