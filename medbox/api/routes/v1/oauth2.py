# medbox/api/routes/auth_router_v1.py

import urllib.parse
from fastapi import APIRouter, Depends, Query, HTTPException, Cookie
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel

from medbox.core.config.settings import settings
from medbox.core.services.security import (
    SecurityService,
    get_security_service,
)

router = APIRouter(prefix="/oauth2", tags=["OAuth2"])


@router.get("/")
async def login(
        redirect_uri: str = Query(None),
        security: SecurityService = Depends(get_security_service),
):
    """Redirige vers Keycloak pour login."""
    state = urllib.parse.quote_plus(redirect_uri) if redirect_uri else ""
    backend_uri=f"{settings.app_url}{settings.url_prefix}/v1/oauth2/callback"

    auth_url = (
        f"{security.authorization_endpoint}"
        f"?client_id={settings.keycloak_client_id}"
        f"&response_type=code&scope=openid profile email"
        f"&redirect_uri={urllib.parse.quote_plus(backend_uri)}"
        f"&state={state}"
    )
    return RedirectResponse(auth_url)


@router.get("/callback")
async def callback(
        code: str,
        state: str | None = None,
        security: SecurityService = Depends(get_security_service),
):
    """Callback Keycloak → échange code contre token"""

    claims, access_token, refresh_token = await security.exchange_code(code)

    # Si "state" contient une URL → redirect vers cette URL
    if state:
        redirect_url = urllib.parse.unquote_plus(state)
        response = RedirectResponse(redirect_url)
    else:
        response = JSONResponse({"access_token": access_token})

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


@router.get("/logout")
async def logout(
        id_token_hint: str,
        security: SecurityService = Depends(get_security_service),
):
    """Logout côté Keycloak"""
    logout_url = (
        f"{security.logout_endpoint}"
        f"?post_logout_redirect_uri={settings.APP_URL}/"
        f"&id_token_hint={id_token_hint}"
    )
    return RedirectResponse(logout_url)
