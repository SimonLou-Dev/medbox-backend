from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from medbox.api.routes.router_v1 import router_v1
from medbox.core.config.settings import settings

app = FastAPI(title="MedBox API", root_path=settings.url_prefix)
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
    print("🚀 API server started")

    # Run database migrations
    print("📦 Running database migrations...")
    try:
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        print("✅ Migrations completed successfully")
    except Exception as e:
        print(f"⚠️  Migration error: {e}")
        raise

    # Initialize scheduler for medication sync
    print("⏰ Syncing medications from API: medicaments-api.giygas.dev...")
    try:
        from medbox.core.tasks.medication_sync import sync_medications_from_api

        sync_medications_from_api.send()
    except Exception as e:
        print(f"⚠️  Medication sync error: {e}")
        raise


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
