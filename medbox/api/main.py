from fastapi import FastAPI

from medbox.api.routes.router_v1 import router_v1
from medbox.core.config.settings import settings

app = FastAPI(title="MedBox API", root_path=settings.url_prefix)
app.include_router(router_v1)


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
    print("⏰ Initializing medication sync scheduler...")
    try:
        from medbox.core.tasks.scheduler import init_scheduler

        init_scheduler()
        print("✅ Scheduler initialized (daily sync at 2 AM)")
    except Exception as e:
        print(f"⚠️  Scheduler initialization warning: {e}")


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
