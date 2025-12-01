"""Initialisation des services Medbox."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from medbox.core.db.repositories.invitation import InvitationRepository
from medbox.core.db.repositories.tenant import TenantRepository
from medbox.core.db.repositories.user import UserRepository
from medbox.core.services.security import (
    SecurityService,
    UserContext,
    get_security_service,
    oauth2_scheme,
    optional_user,
    require_roles,
    require_user,
)
from medbox.core.services.tenant import TenantService
from medbox.core.services.tenant_invitation import TenantInvitationService
from medbox.core.services.tenant_right import (
    TenantRightService,
    require_tenant_role,
    require_user_in_tenant,
    require_user_in_tenant_with_role,
)
from medbox.core.services.user import UserService

# ---------------------------------------------------------------------------
# Instanciation centrale des repositories
# ---------------------------------------------------------------------------

user_repo = UserRepository()
tenant_repo = TenantRepository()

# ==============================================================================
# Service Factories (pas d'instances globales !)
# ==============================================================================


def get_user_service() -> UserService:
    """Crée Factory pour le service utilisateur."""
    return UserService(UserRepository())


def get_tenant_invitation_service() -> TenantInvitationService:
    """Crée Factory pour le service d'invitation."""
    return TenantInvitationService(
        UserRepository(),
        TenantRepository(),
        InvitationRepository(),
    )


def get_tenant_right_service() -> TenantRightService:
    """Crée Factory pour le service des droits."""
    return TenantRightService(UserRepository(), TenantRepository())


def get_tenant_service(
    tenant_invit_svc: Annotated[
        TenantInvitationService,
        Depends(get_tenant_invitation_service),
    ],
    tenant_right_svc: Annotated[TenantRightService, Depends(get_tenant_right_service)],
) -> TenantService:
    """Crée Factory pour le service tenant."""
    return TenantService(
        user_repo=UserRepository(),
        tenant_repo=TenantRepository(),
        tenant_invit_svc=tenant_invit_svc,
        tenant_right_svc=tenant_right_svc,
    )


# ==============================================================================
# Type Aliases pour simplifier l'usage
# ==============================================================================

# Services
SecuritySvcDep = Annotated[SecurityService, Depends(get_security_service)]
UserSvcDep = Annotated[UserService, Depends(get_user_service)]
TenantSvcDep = Annotated[TenantService, Depends(get_tenant_service)]
TenantInvitSvcDep = Annotated[
    TenantInvitationService,
    Depends(get_tenant_invitation_service),
]
TenantRightSvcDep = Annotated[TenantRightService, Depends(get_tenant_right_service)]

# Authentification
CurrentUser = Annotated[UserContext, Depends(require_user)]
OptionalUser = Annotated[UserContext | None, Depends(optional_user)]
