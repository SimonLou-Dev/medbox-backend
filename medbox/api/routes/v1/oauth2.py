"""Router pour l'authentification OAuth2 via Keycloak."""

import urllib.parse
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse, RedirectResponse

from medbox.api.dto.auth import MeResponse, RefreshTokenRequest, TokenResponse
from medbox.core.config.settings import settings
from medbox.core.services.security import (
    CurrentUser,
    SecurityDep,
)
from medbox.core.services.user import UserService

router = APIRouter(prefix="/oauth2", tags=["OAuth2"])

# ==============================================================================
# Type Aliases
# ==============================================================================

UserServiceDep = Annotated[UserService, Depends(UserService)]

# ==============================================================================
# Routes
# ==============================================================================


@router.get("/login")
async def login(
    security: SecurityDep,
    redirect_uri: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    """Redirige vers la page de connexion Keycloak.

    Args:
        security: Service de gestion de l'auth
        redirect_uri: URL de redirection après authentification (optionnel)

    Returns:
        Redirection vers Keycloak

    """
    backend_callback = f"{settings.app_url}{settings.url_prefix}/v1/oauth2/callback"

    # Paramètres de base
    params = {
        "client_id": settings.keycloak_client_id,
        "response_type": "code",
        "scope": "openid profile email",
        "redirect_uri": backend_callback,
    }

    # Ajouter le state si redirect_uri fourni
    if redirect_uri:
        params["state"] = redirect_uri

    query_string = urllib.parse.urlencode(params)
    auth_url = f"{security.authorization_endpoint}?{query_string}"

    return RedirectResponse(auth_url)


@router.get("/callback")
async def callback(
    code: Annotated[str, Query()],
    security: SecurityDep,
    user_service: UserServiceDep,
    state: Annotated[str | None, Query()] = None,
) -> Response:
    """Retour OAuth2 après authentification Keycloak.

    Échange le code d'autorisation contre des tokens et enregistre l'utilisateur.

    Args:
        security: Service de gestion de l'auth
        user_service: Service de gestion de l'utilisateur
        code: Code d'autorisation OAuth2
        state: URL de redirection encodée (optionnel)

    Returns:
        Redirection vers l'URL du state ou JSON avec les tokens

    """
    # Échange du code contre les tokens
    ctx, access_token, refresh_token = await security.exchange_code(code)

    # Enregistrement/mise à jour de l'utilisateur en DB
    await user_service.register_user(ctx)

    # Préparer la réponse (redirect ou JSON)
    if state:
        redirect_url = urllib.parse.unquote_plus(state)
        response = RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)
    else:
        response = JSONResponse(
            content={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
            },
        )

    # Configurer les cookies d'authentification
    _set_auth_cookies(response, access_token, refresh_token or "")

    return response


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    security: SecurityDep,
    body: RefreshTokenRequest,
    cookie_refresh: Annotated[str | None, Cookie(alias="refresh_token")] = None,
) -> JSONResponse:
    """Rafraîchit l'access token.

    Le refresh token peut être fourni soit dans le body, soit dans un cookie.

    Args:
        security: Service de gestion de l'auth
        body: Corps de la requête contenant optionnellement le refresh_token
        cookie_refresh: Refresh token depuis les cookies

    Returns:
        Nouveaux tokens

    Raises:
        HTTPException: Si aucun refresh token n'est fourni

    """
    refresh = body.refresh_token or cookie_refresh
    if not refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided",
        )

    # Rafraîchir les tokens
    tokens = await security.refresh_token(refresh)

    # Préparer la réponse
    response = JSONResponse(
        content={
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "token_type": tokens.token_type,
        },
    )

    # Mettre à jour les cookies
    _set_auth_cookies(
        response,
        tokens.access_token,
        tokens.refresh_token or refresh,
    )

    return response


@router.post("/logout")
async def logout(
    security: SecurityDep,
    _: CurrentUser,
    id_token_hint: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    """Déconnecte l'utilisateur de Keycloak.

    Args:
        _: Contexte de l'utilisateur
        security: Service de gestion de l'auth
        id_token_hint: Token ID pour améliorer la déconnexion (optionnel)

    Returns:
        Redirection vers la page de déconnexion Keycloak

    """
    # Construire l'URL de logout
    params = {
        "post_logout_redirect_uri": f"{settings.app_url}/",
    }

    if id_token_hint:
        params["id_token_hint"] = id_token_hint

    query_string = urllib.parse.urlencode(params)
    logout_url = f"{security.logout_endpoint}?{query_string}"

    # Créer la réponse de redirection
    response = RedirectResponse(logout_url)

    # Supprimer les cookies
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

    return response


@router.get("/me", response_model=MeResponse)
async def get_current_user(
    user: CurrentUser,
    user_service: UserServiceDep,
) -> MeResponse:
    """Retourne les informations de l'utilisateur connecté.

    Combine les données JWT et les données de la base de données.

    Returns:
        Informations complètes de l'utilisateur

    """
    # Récupérer l'utilisateur depuis la DB
    db_user = await user_service.get_user_from_subject(user.subject)

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in database",
        )

    # Construire la réponse
    return MeResponse(
        subject=user.subject,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        roles=user.roles,
        tenant_id=db_user.tenant_id if hasattr(db_user, "tenant_id") else None,
        status=db_user.status if hasattr(db_user, "status") else "active",
        created_at=db_user.created_at if hasattr(db_user, "created_at") else None,
    )


# ==============================================================================
# Helper Functions
# ==============================================================================


def _set_auth_cookies(
    response: RedirectResponse | JSONResponse,
    access_token: str,
    refresh_token: str,
) -> None:
    """Configure les cookies d'authentification.

    Args:
        response: La réponse HTTP
        access_token: Le token d'accès
        refresh_token: Le token de rafraîchissement

    """
    cookie_config = {
        "httponly": True,
        "secure": settings.environment == "production",
        "samesite": "lax",
        "max_age": 3600,  # 1 heure pour l'access token
    }

    response.set_cookie("access_token", access_token, **cookie_config)
    response.set_cookie(
        "refresh_token",
        refresh_token,
        **{**cookie_config, "max_age": 2592000},  # 30 jours pour le refresh token
    )
