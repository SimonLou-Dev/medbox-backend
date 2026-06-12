"""Tâches Celery de scheduling — conservé pour compatibilité future.

Les tâches dispatch_scheduled_takes et calculate_prescription_scheduling
ont été supprimées : la medbox est autonome et gère ses horaires elle-même
à partir du preload qu'elle reçoit 2x/jour.

Voir : medbox/schedulerworker/tasks/preload.py
"""
