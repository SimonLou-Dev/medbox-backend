"""Router pour l'authentification OAuth2 via Keycloak."""

import secrets
import urllib.parse
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse, RedirectResponse

from medbox.core.config.settings import settings
from medbox.core.dto.auth import (
    ChangePasswordRequest,
    DirectLoginRequest,
    MeResponse,
    RegisterRequest,
    UpdateProfileRequest,
)
from medbox.core.services import CurrentUser, SecuritySvcDep, UserSvcDep

router = APIRouter(prefix="/oauth2", tags=["OAuth2"])

# ==============================================================================
# Routes
# ==============================================================================


@router.get("/csrf-token")
async def get_csrf_token() -> Response:
    """Génère un token CSRF pour les utilisateurs non authentifiés.

    Permet aux pages login/register d'obtenir un cookie csrf_token
    avant de soumettre un POST, afin que le middleware CSRF puisse
    vérifier la correspondance cookie ↔ header.

    Returns:
        204 avec cookie csrf_token

    """
    csrf = secrets.token_urlsafe(32)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.set_cookie(
        "csrf_token",
        csrf,
        httponly=False,
        secure=True,
        samesite="none",
        path="/",
        max_age=2592000,
    )
    # Exposer le token dans le header pour que l'intercepteur axios
    # puisse le capturer (le middleware ne le fait pas sur cette requête
    # car le cookie n'existe pas encore dans la requête entrante).
    response.headers["X-CSRF-Token"] = csrf
    return response


@router.get("/login")
async def login(
    security: SecuritySvcDep,
    redirect_uri: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    """Redirige vers la page de connexion Keycloak.

    Args:
        security: Service de gestion de l'auth
        redirect_uri: URL de redirection après authentification (optionnel)

    Returns:
        Redirection vers Keycloak

    """
    backend_callback = f"{settings.app_url}"

    if settings.url_prefix:
        backend_callback += f"{settings.url_prefix}"
    backend_callback += "/v1/oauth2/callback"

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


@router.get("/callback", response_model=MeResponse)
async def callback(
    code: Annotated[str, Query()],
    security: SecuritySvcDep,
    user_service: UserSvcDep,
    state: Annotated[str | None, Query()] = None,
) -> MeResponse:
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
    ctx, access_token, refresh_token, id_token = await security.exchange_code(code)

    # Enregistrement/mise à jour de l'utilisateur en DB
    await user_service.sync_user_from_identity_provider(ctx)

    # Préparer la réponse (redirect ou JSON)
    if state:
        redirect_url = urllib.parse.unquote_plus(state)
        response = RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)
    else:
        response = Response(status_code=status.HTTP_204_NO_CONTENT)

    # Configurer les cookies d'authentification
    _set_auth_cookies(response, access_token, refresh_token or "", id_token or "")

    return response


@router.post("/direct-login")
async def direct_login(
    body: DirectLoginRequest,
    security: SecuritySvcDep,
    user_service: UserSvcDep,
) -> Response:
    """Connexion directe via username/password.

    Authentifie l'utilisateur via le Resource Owner Password Credentials flow
    de Keycloak et retourne les tokens dans des cookies HTTP-only.

    Args:
        body: Username et password
        security: Service de gestion de l'auth
        user_service: Service de gestion de l'utilisateur

    Returns:
        204 avec cookies d'authentification

    """
    # Authentification via Keycloak
    ctx, access_token, refresh_token, id_token = await security.authenticate_with_password(
        username=body.username,
        password=body.password,
    )

    # Synchro utilisateur en DB (identique au callback OAuth2)
    await user_service.sync_user_from_identity_provider(ctx)

    # Réponse avec cookies
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _set_auth_cookies(response, access_token, refresh_token or "", id_token or "")

    return response


@router.post("/register")
async def register(
    body: RegisterRequest,
    security: SecuritySvcDep,
    user_service: UserSvcDep,
) -> Response:
    """Inscription d'un nouvel utilisateur.

    Crée l'utilisateur dans Keycloak via l'Admin API, puis l'authentifie
    automatiquement et synchronise les données en base.

    Args:
        body: Données d'inscription
        security: Service de gestion de l'auth
        user_service: Service de gestion de l'utilisateur

    Returns:
        204 avec cookies d'authentification

    """
    # 1. Créer l'utilisateur dans Keycloak
    await security.register_user(
        email=body.email,
        password=body.password,
        first_name=body.first_name,
        last_name=body.last_name,
        username=body.username,
    )

    # 2. Authentifier automatiquement le nouvel utilisateur
    ctx, access_token, refresh_token, id_token = await security.authenticate_with_password(
        username=body.username,
        password=body.password,
    )

    # 3. Synchro en DB (crée le user avec status=PENDING, role=DEFAULT, tenant_id=NULL)
    await user_service.sync_user_from_identity_provider(ctx)

    # 4. Réponse avec cookies
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _set_auth_cookies(response, access_token, refresh_token or "", id_token or "")

    return response


@router.post(
    "/refresh",
)
async def refresh_token(
    security: SecuritySvcDep,
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
    if not cookie_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided",
        )

    # Rafraîchir les tokens
    tokens = await security.refresh_token(cookie_refresh)

    # Préparer la réponse
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    # Mettre à jour les cookies
    _set_auth_cookies(
        resp,
        tokens.access_token,
        tokens.refresh_token,
    )

    return resp


@router.post("/logout")
async def logout(
    security: SecuritySvcDep,
    _: CurrentUser,
    redirect_uri: Annotated[str | None, Query()] = None,
    id_token_hint: Annotated[str | None, Query()] = None,
    id_token_cookie: Annotated[str | None, Cookie(alias="id_token")] = None,
) -> JSONResponse:
    """Déconnecte l'utilisateur de Keycloak.

    Args:
        _: Contexte de l'utilisateur
        security: Service de gestion de l'auth
        redirect_uri: URL de redirection après logout Keycloak (optionnel)
        id_token_hint: Token ID pour améliorer la déconnexion (optionnel)

    Returns:
        JSON avec l'URL de déconnexion Keycloak

    """
    # Construire l'URL de logout
    post_logout_uri = redirect_uri or f"{settings.app_url}/"
    params = {
        "client_id": settings.keycloak_client_id,
        "post_logout_redirect_uri": post_logout_uri,
    }

    # Utiliser l'id_token du cookie si disponible (priorité au query param)
    id_token = id_token_hint or id_token_cookie
    if id_token:
        params["id_token_hint"] = id_token

    query_string = urllib.parse.urlencode(params)
    logout_url = f"{security.logout_endpoint}?{query_string}"

    # Créer la réponse JSON (pas de redirect, pour que les Set-Cookie
    # soient correctement traités par le navigateur en cross-origin)
    response = JSONResponse(content={"logout_url": logout_url})

    # Supprimer les cookies avec les mêmes attributs qu'à la création
    cookie_delete_config = {
        "httponly": True,
        "secure": True,
        "samesite": "none",
    }
    response.delete_cookie("access_token", **cookie_delete_config)
    response.delete_cookie("refresh_token", **cookie_delete_config)
    response.delete_cookie("id_token", **cookie_delete_config)
    response.delete_cookie("csrf_token", secure=True, samesite="none")

    return response


@router.put("/profile")
async def update_profile(
    body: UpdateProfileRequest,
    user: CurrentUser,
    security: SecuritySvcDep,
    user_service: UserSvcDep,
) -> Response:
    """Met à jour le profil de l'utilisateur connecté.

    Modifie le prénom, nom et/ou email dans Keycloak, puis
    re-synchronise les données en base.

    Args:
        body: Champs à modifier
        user: Contexte de l'utilisateur connecté
        security: Service de sécurité
        user_service: Service utilisateur

    Returns:
        204 No Content

    """
    await security.update_user_profile(
        subject=user.subject,
        first_name=body.first_name,
        last_name=body.last_name,
        email=body.email,
    )

    # Re-sync en DB avec les nouvelles données Keycloak
    # On re-construit le full_name à partir des champs fournis ou existants
    new_full_name = user.full_name
    if body.first_name is not None or body.last_name is not None:
        given = body.first_name if body.first_name is not None else user.claims.get("given_name", "")
        family = body.last_name if body.last_name is not None else user.claims.get("family_name", "")
        new_full_name = f"{given} {family.upper()}".strip()

    new_email = body.email if body.email is not None else user.email

    await user_service.user_repo.update_or_create(
        filters={"keycloak_subject": user.subject},
        defaults={
            "email": new_email,
            "c_full_name": new_full_name,
        },
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/password")
async def change_password(
    body: ChangePasswordRequest,
    user: CurrentUser,
    security: SecuritySvcDep,
) -> Response:
    """Change le mot de passe de l'utilisateur connecté.

    Vérifie d'abord l'ancien mot de passe avant d'appliquer le nouveau.

    Args:
        body: Ancien et nouveau mot de passe
        user: Contexte de l'utilisateur connecté
        security: Service de sécurité

    Returns:
        204 No Content

    """
    await security.change_user_password(
        subject=user.subject,
        username=user.username,
        current_password=body.current_password,
        new_password=body.new_password,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=MeResponse)
async def get_current_user(
    user: CurrentUser,
    user_service: UserSvcDep,
) -> MeResponse:
    """Retourne les informations de l'utilisateur connecté.

    Combine les données JWT et les données de la base de données.

    Returns:
        Informations complètes de l'utilisateur

    """
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
        realm_roles=user.roles,
        role=db_user.role,
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
    id_token: str = "",
) -> None:
    """Configure les cookies d'authentification.

    Args:
        response: La réponse HTTP
        access_token: Le token d'accès
        refresh_token: Le token de rafraîchissement
        id_token: Le token d'identité (pour le logout Keycloak)

    """
    cookie_config = {
        "httponly": True,
        "secure": True,
        "samesite": "none",
        "max_age": 3600,  # 1 heure pour l'access token
    }

    response.set_cookie("access_token", access_token, **cookie_config)
    response.set_cookie(
        "refresh_token",
        refresh_token,
        **{**cookie_config, "max_age": 2592000},  # 30 jours pour le refresh token
    )

    if id_token:
        response.set_cookie(
            "id_token",
            id_token,
            **{**cookie_config, "max_age": 2592000},  # 30 jours
        )

    csrf = secrets.token_urlsafe(32)
    response.set_cookie(
        "csrf_token",
        csrf,
        httponly=False,
        secure=True,
        samesite="none",
        path="/",
        max_age=2592000,
    )
