from fastapi import FastAPI

from medbox.api.routes.router_v1 import router_v1
from medbox.core.config.settings import settings

app = FastAPI(title="MedBox API", root_path=settings.url_prefix)
app.include_router(router_v1)


def run():
    import uvicorn

    uvicorn.run("medbox.api.main:app", host="0.0.0.0", port=8000)


def run_dev():
    import uvicorn

    uvicorn.run(
        "medbox.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["medbox/api", "medbox/core"],
        reload_excludes=["medbox/schedulerworker"],
    )
