"""Définitions des routes API v1."""

from fastapi import APIRouter

from medbox.api.routes.v1.health import health_router_v1
from medbox.api.routes.v1.oauth2 import router as oauth2_router
from medbox.api.routes.v1.tenant import router as tenant_router

router_v1 = APIRouter(prefix="/v1")

router_v1.include_router(health_router_v1)
router_v1.include_router(oauth2_router)
router_v1.include_router(tenant_router)
