from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List

import httpx
from authlib.jose import JsonWebKey, jwt
from fastapi import HTTPException, Request, Response, Depends
from fastapi.security import OAuth2AuthorizationCodeBearer
from fastapi.security.utils import get_authorization_scheme_param
from pydantic import BaseModel
from starlette import status

from medbox.core.config.settings import settings

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/auth",
    tokenUrl=f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/token",
)

class SecurityService:
    """
    Service de sécurité intégrant :
    - Découverte OIDC
    - Décodage token JWT
    - Rafraîchissement via refresh_token
    - Récupération des rôles
    - Appels Account API
    """

    def __init__(self):
        realm = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}"
        self.oidc_base = f"{realm}/protocol/openid-connect"

        self.authorization_endpoint = f"{self.oidc_base}/auth"
        self.token_endpoint = f"{self.oidc_base}/token"
        self.userinfo_endpoint = f"{self.oidc_base}/userinfo"
        self.logout_endpoint = f"{self.oidc_base}/logout"
        self.jwks_uri = f"{self.oidc_base}/certs"

        self._jwks_cache: Optional[JsonWebKey] = None
        self._jwks_fetched_at: Optional[datetime] = None
        self._jwks_lock = asyncio.Lock()
        self._jwks_ttl = timedelta(minutes=30)

    # ------------------------------------------------------------------
    # JWKS fetching
    # ------------------------------------------------------------------

    async def _fetch_jwks(self) -> JsonWebKey:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(self.jwks_uri)

        if resp.status_code != 200:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Unable to fetch JWKS from Keycloak",
            )

        return JsonWebKey.import_key_set(resp.json())

    async def get_jwks(self) -> JsonWebKey:
        if self._jwks_cache and self._jwks_fetched_at:
            if datetime.now() - self._jwks_fetched_at < self._jwks_ttl:
                return self._jwks_cache

        async with self._jwks_lock:
            # Re-check inside lock
            if self._jwks_cache and self._jwks_fetched_at:
                if datetime.now() - self._jwks_fetched_at < self._jwks_ttl:
                    return self._jwks_cache

            self._jwks_cache = await self._fetch_jwks()
            self._jwks_fetched_at = datetime.now()
            return self._jwks_cache

    # ------------------------------------------------------------------
    # JWT
    # ------------------------------------------------------------------

    async def decode_token(self, token: str) -> Dict[str, Any]:
        try:
            keys = await self.get_jwks()
            claims = jwt.decode(token, keys)
            claims.validate()
            return dict(claims)
        except Exception as e:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                f"Invalid or expired token: {e}",
            )

    # ------------------------------------------------------------------
    # Exchange code
    # ------------------------------------------------------------------

    async def exchange_code(self, code: str):
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                self.token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": settings.keycloak_client_id,
                    "client_secret": settings.keycloak_client_secret,
                    "redirect_uri": f"{settings.app_url}{settings.url_prefix}/v1/oauth2/callback",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if resp.status_code != 200:
            raise HTTPException(401, resp.json())

        tokens = resp.json()
        claims = await self.decode_token(tokens["access_token"])
        ctx = LightWeightUserContext(claims=claims)
        return ctx, tokens["access_token"], tokens.get("refresh_token")

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    async def refresh(self, refresh_token: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                self.token_endpoint,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": settings.keycloak_client_id,
                    "client_secret": settings.keycloak_client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if resp.status_code != 200:
            raise HTTPException(401, resp.json())

        return resp.json()

    # ------------------------------------------------------------------
    # Roles
    # ------------------------------------------------------------------

    @staticmethod
    def get_roles(claims: Dict[str, Any]) -> List[str]:
        roles = claims.get("realm_access", {}).get("roles", []) or []
        client_roles = (
                claims.get("resource_access", {})
                .get(settings.keycloak_client_id, {})
                .get("roles", [])
                or []
        )
        return list(roles) + list(client_roles)

    # ------------------------------------------------------------------
    # User Context
    # ------------------------------------------------------------------

    async def get_current_user(self, request: Request, response: Response):
        token = self.extract_token(request)
        if not token:
            raise HTTPException(401, "Not authenticated")

        try:
            claims = await self.decode_token(token)
            return UserContext(claims=claims, token=token)
        except HTTPException:
            # try silent refresh
            refresh_token = request.cookies.get("refresh_token")
            if not refresh_token:
                raise

            tokens = await self.refresh(refresh_token)
            new_access = tokens["access_token"]
            new_refresh = tokens.get("refresh_token", refresh_token)

            # update cookies
            response.set_cookie(
                "access_token",
                new_access,
                httponly=True,
                secure=False,
                samesite='lax',
            )
            response.set_cookie(
                "refresh_token",
                new_refresh,
                httponly=True,
                secure=False,
                samesite="lax",
            )

            claims = await self.decode_token(new_access)
            return UserContext(claims=claims, token=new_access)

    async def get_current_user_optional(
            self, request: Request, response: Response
    ) -> Optional[UserContext]:
        token = self.extract_token(request)
        if not token:
            return None
        return await self.get_current_user(request, response)

    @staticmethod
    def extract_token(request: Request) -> str | None:
        """
        Extrait un JWT soit de l'Authorization header, soit du cookie.
        Priorité à l'Authorization header.
        """
        auth = request.headers.get("Authorization")
        if auth:
            scheme, param = get_authorization_scheme_param(auth)
            if scheme and scheme.lower() == "bearer" and param:
                return param

        token = request.cookies.get("access_token")
        if token:
            return token

        return None

class LightWeightUserContext(BaseModel):
    claims: Dict[str, Any]
    @property
    def subject(self) -> str:
        return self.claims.get("sub")

    @property
    def username(self) -> str:
        return self.claims.get("username")
    
    @property
    def full_name(self) -> str:
        return self.claims.get("given_name") + " " + self.claims.get("family_name").upper()

    @property
    def email(self) -> str | None:
        return self.claims.get("email")

    @property
    def roles(self) -> List[str]:
        svc = SecurityService()  # pas idéal mais ok pour les getters
        return svc.get_roles(self.claims)

class UserContext(LightWeightUserContext):
    token: str



def get_security_service() -> SecurityService:
    return SecurityService()


async def require_user(
        request: Request,
        response: Response,
        svc: SecurityService = Depends(get_security_service),
) -> UserContext:
    return await svc.get_current_user(request, response)


def require_roles(*expected: str):
    expected_roles = set(expected)

    async def dependency(
            request: Request,
            response: Response,
            svc: SecurityService = Depends(get_security_service),
    ) -> UserContext:
        user = await svc.get_current_user(request, response)
        if not set(user.roles).intersection(expected_roles):
            raise HTTPException(403, "Insufficient permissions")
        return user

    return dependency