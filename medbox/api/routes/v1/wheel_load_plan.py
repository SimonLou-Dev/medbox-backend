"""Endpoints pour les plans de chargement de roue."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from medbox.core.dto.wheel_load_plan import (
    WheelLoadPlanConfirmRequest,
    WheelLoadPlanCreateRequest,
    WheelLoadPlanDetailResponse,
    WheelLoadPlanResponse,
)
from medbox.core.db.models import User
from medbox.core.services import CurrentUser, get_user_service
from medbox.core.services.user import UserService
from medbox.core.services.wheel_load_plan import WheelLoadPlanService

router = APIRouter(tags=["Wheel Load Plans"])


async def get_current_db_user(
    user: CurrentUser,
    user_svc: Annotated[UserService, Depends(get_user_service)],
) -> User:
    """Resout l'utilisateur Medbox (DB) depuis le subject du JWT."""
    return await user_svc.get_user_from_subject(user.subject)


CurrentDbUser = Annotated[User, Depends(get_current_db_user)]


async def get_wheel_load_plan_service(
    db_user: CurrentDbUser,
) -> WheelLoadPlanService:
    return WheelLoadPlanService(tenant_id=db_user.tenant_id)


WheelLoadPlanSvcDep = Annotated[
    WheelLoadPlanService, Depends(get_wheel_load_plan_service)
]


@router.get(
    "/wheel-load-plans",
    response_model=list[WheelLoadPlanResponse],
    summary="Lister les plans de chargement",
)
async def list_plans(
    svc: WheelLoadPlanSvcDep,
) -> list[WheelLoadPlanResponse]:
    """Liste tous les plans de chargement du tenant."""
    return await svc.list()


@router.post(
    "/wheel-load-plans",
    response_model=WheelLoadPlanDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un plan de chargement (moulinette)",
)
async def create_plan(
    body: WheelLoadPlanCreateRequest,
    db_user: CurrentDbUser,
    svc: WheelLoadPlanSvcDep,
) -> WheelLoadPlanDetailResponse:
    """Croise les ordonnances sélectionnées et calcule la répartition dans les 21 cases.

    Retourne la liste de remplissage que le soignant utilise pour charger la roue.
    Le plan reste en statut 'draft' jusqu'à confirmation (POST /confirm).
    """
    return await svc.create(body, created_by_user_id=db_user.id)


@router.get(
    "/wheel-load-plans/{plan_id}",
    response_model=WheelLoadPlanDetailResponse,
    summary="Récupérer un plan avec sa liste de remplissage",
)
async def get_plan(
    plan_id: UUID,
    svc: WheelLoadPlanSvcDep,
) -> WheelLoadPlanDetailResponse:
    """Récupère un plan existant avec la liste complète des cases à remplir."""
    return await svc.get_filling_list(plan_id)


@router.post(
    "/wheel-load-plans/{plan_id}/confirm",
    response_model=WheelLoadPlanResponse,
    summary="Confirmer le remplissage physique de la roue",
)
async def confirm_plan(
    plan_id: UUID,
    body: WheelLoadPlanConfirmRequest,
    db_user: CurrentDbUser,
    svc: WheelLoadPlanSvcDep,
) -> WheelLoadPlanResponse:
    """Confirme que le soignant a physiquement chargé la roue.

    Crée les PrescriptionScheduleItems, assigne la roue à la medbox
    et passe le plan en statut 'active'.
    """
    return await svc.confirm(plan_id, body, user_id=db_user.id)
