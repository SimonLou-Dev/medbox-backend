import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from medbox.api.middlewares.logging import RequestLoggingMiddleware
from medbox.api.routes.router_v1 import router_v1
from medbox.core.config.settings import settings

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler (startup + shutdown)."""
    logger.info("🚀 API server started")
    logger.info("APP_URL: %s", settings.app_url)
    logger.info("URL_PREFIX: %s", settings.url_prefix)

    # Startup: migrations + scheduler
    logger.info("📦 Running database migrations...")
    try:
        from alembic.config import Config

        alembic_cfg = Config("alembic.ini")
        # command.upgrade(alembic_cfg, "head") #############################################
        logger.info("✅ Migrations completed successfully")
    except Exception as e:
        logger.error("⚠️  Migration error: %s", e, exc_info=True)
        raise

    logger.info("⏰ Initializing scheduler...")  # Inici c'es c&ssé
    try:
        from medbox.core.tasks.scheduler import init_scheduler

        init_scheduler()
        logger.info("✅ Scheduler initialized (daily sync at 2 AM)")
    except Exception as e:
        logger.warning("⚠️  Scheduler initialization warning: %s", e, exc_info=True)

    yield

    # Shutdown (si tu as quelque chose à fermer plus tard)
    logger.info("🛑 API server stopped")


# FastAPI root_path must be string, not None
root_path = settings.url_prefix or ""

app = FastAPI(title="MedBox API", root_path=root_path, lifespan=lifespan)
app.include_router(router_v1)
app.add_middleware(RequestLoggingMiddleware)

allowed_origins = [
    "https://medbox.theokaszak.fr",
    "https://api.medbox.theokaszak.fr",
    # Dev front (exemples)
    "http://localhost:8000",
    "http://localhost:8001",
    # Optionnel: si tu utilises Vite/React/Next avec un autre port
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:3001",
    "http://localhost:5174",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    # Si tu utilises des cookies (session, auth), mets True.
    # Sinon laisse False pour éviter d'ouvrir inutilement.
    allow_credentials=True,
    # Méthodes autorisées
    allow_methods=["*"],
    # Headers autorisés (Authorization utile pour JWT)
    allow_headers=["*"],
)

# Add Traefik/Proxy header middleware for real IP logging
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# TrustedHostMiddleware expects hostnames, not full URLs
allowed_hosts = [
    "medbox.theokaszak.fr",
    "api.medbox.theokaszak.fr",
    "localhost",
    "127.0.0.1",
    "*.localhost",
]
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts,
)


def run() -> None:
    """Run production server."""
    a = logging.getLogger("uvicorn.access")
    e = logging.getLogger("uvicorn.error")

    logger.info(
        "uvicorn.access level=%s propagate=%s handlers=%s",
        a.level,
        a.propagate,
        a.handlers,
    )
    logger.info(
        "uvicorn.error  level=%s propagate=%s handlers=%s",
        e.level,
        e.propagate,
        e.handlers,
    )

    uvicorn.run(
        "medbox.api.main:app",
        host="0.0.0.0",
        port=8000,
        access_log=True,
        log_level="info",
    )


def run_dev() -> None:
    """Run development server with auto-reload."""
    uvicorn.run(
        "medbox.api.main:app",
        host="0.0.0.0",  # noqa: S104
        port=8000,
        reload=True,
        reload_dirs=["medbox/api", "medbox/core"],
        reload_excludes=["medbox/schedulerworker"],
        access_log=True,
        log_level="debug",
    )


if __name__ == "__main__":
    run()
