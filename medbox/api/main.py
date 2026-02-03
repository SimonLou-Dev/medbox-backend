import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from medbox.api.routes.router_v1 import router_v1
from medbox.core.config.settings import settings

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger(__name__)

# FastAPI root_path must be string, not None
root_path = settings.url_prefix or ""

app = FastAPI(title="MedBox API", root_path=root_path)
app.include_router(router_v1)

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


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize database migrations and scheduler on app startup.

    1. Runs pending database migrations via Alembic
    2. Initializes APScheduler to send Dramatiq tasks at 2 AM daily
    """
    logger.info("🚀 API server started")
    logger.info(f"APP_URL: {settings.app_url}")
    logger.info(f"URL_PREFIX: {settings.url_prefix}")

    # Run database migrations
    logger.info("📦 Running database migrations...")
    try:
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("✅ Migrations completed successfully")
    except Exception as e:
        logger.error(f"⚠️  Migration error: {e}", exc_info=True)
        raise

    # Initialize scheduler for medication sync
    logger.info("⏰ Initializing scheduler...")
    try:
        from medbox.core.tasks.scheduler import init_scheduler

        init_scheduler()
        logger.info("✅ Scheduler initialized (daily sync at 2 AM)")
    except Exception as e:
        logger.warning(f"⚠️  Scheduler initialization warning: {e}", exc_info=True)


def run() -> None:
    """Run production server."""
    import uvicorn

    uvicorn.run("medbox.api.main:app", host="0.0.0.0", port=8000)  # noqa: S104


def run_dev() -> None:
    """Run development server with auto-reload."""
    import uvicorn

    uvicorn.run(
        "medbox.api.main:app",
        host="0.0.0.0",  # noqa: S104
        port=8000,
        reload=True,
        reload_dirs=["medbox/api", "medbox/core"],
        reload_excludes=["medbox/schedulerworker"],
    )
