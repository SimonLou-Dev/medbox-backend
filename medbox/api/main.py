from fastapi import FastAPI

from medbox.api.routes.router_v1 import router_v1
from medbox.core.config.settings import settings

app = FastAPI(title="MedBox API", root_path=settings.url_prefix)
app.include_router(router_v1)


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize scheduler on app startup.

    The scheduler will send Dramatiq tasks to the queue at 2 AM daily.
    If Redis is unavailable, the scheduler initialization is gracefully handled.
    """
    print("API server started")
    print("Lancement de la tâche de fond pour la synchronisation des médicaments.")

    from medbox.core.tasks.medication_sync import sync_medications_from_api

    sync_medications_from_api.send()


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
