# medbox/api/routes/auth_router_v1.py

import urllib.parse
from fastapi import APIRouter, Depends, Query, HTTPException, Cookie, Security
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel

from medbox.core.config.settings import settings
from medbox.core.services.security import (
    SecurityService,
    get_security_service, UserContext, require_user, oauth2_scheme,
)
from medbox.core.services.user import UserService

router = APIRouter(prefix="/oauth2", tags=["OAuth2"])


@router.get("/")
async def login(
        redirect_uri: str = Query(None),
        security: SecurityService = Depends(get_security_service),
):
    """Redirige vers Keycloak pour login."""

    backend_uri=f"{settings.app_url}{settings.url_prefix}/v1/oauth2/callback"
    auth_url = None
    if redirect_uri:
        state = urllib.parse.quote_plus(redirect_uri)
        auth_url = (
            f"{security.authorization_endpoint}"
            f"?client_id={settings.keycloak_client_id}"
            f"&response_type=code&scope=openid profile email"
            f"&redirect_uri={urllib.parse.quote_plus(backend_uri)}"
            f"&state={state}"
        )
    else:
        auth_url = (
            f"{security.authorization_endpoint}"
            f"?client_id={settings.keycloak_client_id}"
            f"&response_type=code&scope=openid profile email"
            f"&redirect_uri={urllib.parse.quote_plus(backend_uri)}"
        )
    return RedirectResponse(auth_url)


@router.get("/callback")
async def callback(
        code: str,
        state: str | None = None,
        security: SecurityService = Depends(get_security_service),
        user_service: UserService = Depends(UserService)
):
    """Callback Keycloak → échange code contre token"""

    ctx, access_token, refresh_token = await security.exchange_code(code)

    await user_service.register_user(ctx)


    # Si "state" contient une URL → redirect vers cette URL
    if state:
        redirect_url = urllib.parse.unquote_plus(state)
        response = RedirectResponse(redirect_url)
    else:
        response = JSONResponse({"access_token": access_token, "refresh_token": refresh_token})

    response.set_cookie("access_token", access_token, httponly=True, secure=False, samesite="Lax")
    response.set_cookie("refresh_token", refresh_token, httponly=True, secure=False, samesite="Lax")

    return response


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


@router.post("/refresh")
async def refresh_token(
        body: RefreshRequest,
        cookie_refresh: str | None = Cookie(default=None, alias="refresh_token"),
        security: SecurityService = Depends(get_security_service),
):
    """Refresh manuel de l'access_token (via body JSON ou cookie)."""
    refresh_token = body.refresh_token or cookie_refresh
    if not refresh_token:
        raise HTTPException(401, "No refresh token provided")

    tokens = await security.refresh(refresh_token)

    response = JSONResponse(tokens)
    response.set_cookie("access_token", tokens["access_token"], httponly=True, secure=False, samesite="Lax")
    response.set_cookie("refresh_token", tokens["refresh_token"], httponly=True, secure=False, samesite="Lax")
    return response


@router.get("/logout", dependencies=[Security(oauth2_scheme)])
async def logout(
        id_token_hint: str,
        security: SecurityService = Depends(get_security_service),
        _: UserContext = Depends(require_user),
):
    """Logout côté Keycloak"""
    logout_url = (
        f"{security.logout_endpoint}"
        f"?post_logout_redirect_uri={settings.APP_URL}/"
        f"&id_token_hint={id_token_hint}"
    )
    return RedirectResponse(logout_url)

@router.get("/me", dependencies=[Security(oauth2_scheme)])
async def me(
        user: UserContext = Depends(require_user),
        user_service: UserService = Depends(UserService)
):
    db_user = await user_service.get_user_from_subject(user.subject)
    # TODO un DTO avec les infos (tenant, full_name,  email, status, username)

    return {
        "subject": user.subject,
        "email": user.email,
        "roles": user.roles,
        "claims": user.claims,
        "db": db_user
    }