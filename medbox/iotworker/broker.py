"""Point d'entrée Celery pour l'IoT Worker.

L'IoT Worker consomme exclusivement la queue 'iot'.
Lancement : celery -A medbox.iotworker.broker worker -Q iot -c 4
"""

from celery.signals import worker_process_init

from medbox.core.celery_app import celery_app  # noqa: F401 — expose l'app Celery


@worker_process_init.connect
def reset_db_engine(**kwargs) -> None:
    """Dispose l'engine SQLAlchemy après chaque fork de worker.

    Nécessaire car asyncpg lie ses connexions à l'event loop du processus parent.
    Après fork, chaque worker doit créer ses propres connexions.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from medbox.core.config.settings import settings
    from medbox.core.db import session as db_session

    db_session.engine.sync_engine.dispose(close=False)
    # NullPool : pas de réutilisation de connexion entre les asyncio.run() successifs
    db_session.engine = create_async_engine(
        settings.get_async_db_url(),
        future=True,
        poolclass=NullPool,
    )
    db_session.async_session_local = async_sessionmaker(
        db_session.engine,
        expire_on_commit=False,
        autoflush=False,
    )
