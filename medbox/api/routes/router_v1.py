from fastapi import APIRouter

from .v1.health import health_router_v1
from .v1.oauth2 import router as oauth2_router_v1

router_v1 = APIRouter(prefix="/v1")

router_v1.include_router(health_router_v1)
router_v1.include_router(oauth2_router_v1)