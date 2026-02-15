"""Définitions des routes API v1."""

from fastapi import APIRouter

from medbox.api.routes.v1.admin import router as admin_router
from medbox.api.routes.v1.global_medication import global_medication_router
from medbox.api.routes.v1.health import health_router_v1
from medbox.api.routes.v1.invitation import admin_router as admin_invitation_router
from medbox.api.routes.v1.invitation import router as invitation_router
from medbox.api.routes.v1.oauth2 import router as oauth2_router
from medbox.api.routes.v1.patient import router as patient_router
from medbox.api.routes.v1.prescription import router as prescription_router
from medbox.api.routes.v1.tenant import router as tenant_router

router_v1 = APIRouter(prefix="/v1")


router_v1.include_router(health_router_v1)
router_v1.include_router(invitation_router)
router_v1.include_router(admin_invitation_router)
router_v1.include_router(oauth2_router)
router_v1.include_router(tenant_router)
router_v1.include_router(patient_router)
router_v1.include_router(global_medication_router)
router_v1.include_router(prescription_router)
router_v1.include_router(admin_router)
