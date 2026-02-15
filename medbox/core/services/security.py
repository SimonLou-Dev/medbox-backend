"""Service de sécurité pour l'authentification Keycloak/OIDC."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Annotated, Any

import httpx
from authlib.jose import JsonWebKey, jwt
from authlib.jose.errors import ExpiredTokenError, JoseError
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from fastapi.security.utils import get_authorization_scheme_param
from pydantic import BaseModel

from medbox.core.config.settings import settings

logger = logging.getLogger(__name__)

# ==============================================================================
# OAuth2 Scheme
# ==============================================================================

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/auth",
    tokenUrl=f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/token",
)


# ==============================================================================
# Models
# ==============================================================================


class LightWeightUserContext(BaseModel):
    """Contexte utilisateur léger contenant uniquement les claims JWT."""

    claims: dict[str, Any]

    @property
    def subject(self) -> str:
        """Retourne le subject (sub) du token JWT."""
        return self.claims.get("sub", "")

    @property
    def username(self) -> str:
        """Retourne le username de l'utilisateur."""
        return self.claims.get("preferred_username", "")

    @property
    def full_name(self) -> str:
        """Retourne le nom complet de l'utilisateur."""
        given_name = self.claims.get("given_name", "")
        family_name = self.claims.get("family_name", "").upper()
        return f"{given_name} {family_name}".strip()

    @property
    def email(self) -> str | None:
        """Retourne l'email de l'utilisateur."""
        return self.claims.get("email")

    @property
    def roles(self) -> list[str]:
        """Retourne tous les rôles (realm + client) de l'utilisateur."""
        realm_roles = self.claims.get("realm_access", {}).get("roles", []) or []
        client_roles = (
            self.claims.get("resource_access", {})
            .get(settings.keycloak_client_id, {})
            .get("roles", [])
            or []
        )
        return [*realm_roles, *client_roles]


class UserContext(LightWeightUserContext):
    """Contexte utilisateur complet incluant le token d'accès."""

    token: str


class TokenResponse(BaseModel):
    """Réponse d'échange de token OAuth2."""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"  # noqa: S105
    expires_in: int | None = None


# ==============================================================================
# Security Service
# ==============================================================================


class SecurityService:
    """Service de sécurité gérant l'authentification via Keycloak/OIDC.

    Fonctionnalités :
    - Découverte OIDC et récupération des JWKS
    - Décodage et validation des tokens JWT
    - Échange de code d'autorisation
    - Rafraîchissement des tokens
    - Gestion des rôles utilisateur
    """

    def __init__(self) -> None:
        """Initialise le service avec les endpoints Keycloak."""
        realm_url = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}"
        self.oidc_base = f"{realm_url}/protocol/openid-connect"

        # Endpoints OIDC
        self.authorization_endpoint = f"{self.oidc_base}/auth"
        self.token_endpoint = f"{self.oidc_base}/token"
        self.userinfo_endpoint = f"{self.oidc_base}/userinfo"
        self.logout_endpoint = f"{self.oidc_base}/logout"
        self.jwks_uri = f"{realm_url}/protocol/openid-connect/certs"

        # Cache JWKS
        self._jwks_cache: JsonWebKey | None = None
        self._jwks_fetched_at: datetime | None = None
        self._jwks_lock = asyncio.Lock()
        self._jwks_ttl = timedelta(minutes=30)

    # --------------------------------------------------------------------------
    # JWKS Management
    # --------------------------------------------------------------------------

    async def _fetch_jwks(self) -> JsonWebKey:
        """Récupère les clés publiques JWKS depuis Keycloak."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(self.jwks_uri)

        if response.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to fetch JWKS from Keycloak",
            )

        return JsonWebKey.import_key_set(response.json())

    async def get_jwks(self) -> JsonWebKey:
        """Retourne les clés JWKS en cache ou les récupère si expirées.

        Utilise un cache avec TTL et un lock pour éviter les requêtes simultanées.
        """
        # Fast path: cache valide
        if (
            self._jwks_cache
            and self._jwks_fetched_at
            and datetime.now() - self._jwks_fetched_at < self._jwks_ttl
        ):
            return self._jwks_cache

        # Slow path: refresh avec lock
        async with self._jwks_lock:
            # Double-check après acquisition du lock
            if (
                self._jwks_cache
                and self._jwks_fetched_at
                and datetime.now() - self._jwks_fetched_at < self._jwks_ttl
            ):
                return self._jwks_cache

            self._jwks_cache = await self._fetch_jwks()
            self._jwks_fetched_at = datetime.now()
            return self._jwks_cache

    # --------------------------------------------------------------------------
    # JWT Operations
    # --------------------------------------------------------------------------

    async def decode_token(self, token: str) -> dict[str, Any]:
        """Décode et valide un token JWT.

        Args:
            token: Le token JWT à décoder

        Returns:
            Les claims du token sous forme de dictionnaire

        Raises:
            HTTPException: Si le token est invalide ou expiré

        """
        try:
            keys = await self.get_jwks()
            claims = jwt.decode(token, keys)
            claims.validate()
            return dict(claims)
        except ExpiredTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="token_expired",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e
        except JoseError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="token_invalid",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e
        except Exception as e:
            # erreur inattendue => 500 ou 503 selon ton goût, mais pas 401
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="token_decode_error",
            ) from e

    # --------------------------------------------------------------------------
    # OAuth2 Flow
    # --------------------------------------------------------------------------

    async def exchange_code(
        self,
        code: str,
    ) -> tuple[LightWeightUserContext, str, str | None, str | None]:
        """Échange un code d'autorisation contre des tokens.

        Args:
            code: Le code d'autorisation OAuth2

        Returns:
            Tuple contenant (UserContext, access_token, refresh_token, id_token)

        Raises:
            HTTPException: Si l'échange échoue

        """
        async with httpx.AsyncClient(timeout=5.0) as client:
            backend_callback = f"{settings.app_url}"

            if settings.url_prefix:
                backend_callback += f"{settings.url_prefix}"
            backend_callback += "/v1/oauth2/callback"
            response = await client.post(
                self.token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": settings.keycloak_client_id,
                    "client_secret": settings.keycloak_client_secret,
                    "redirect_uri": backend_callback,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if response.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=response.json(),
            )

        tokens = response.json()
        claims = await self.decode_token(tokens["access_token"])
        user_context = LightWeightUserContext(claims=claims)

        return (
            user_context,
            tokens["access_token"],
            tokens.get("refresh_token"),
            tokens.get("id_token"),
        )

    async def authenticate_with_password(
        self,
        username: str,
        password: str,
    ) -> tuple[LightWeightUserContext, str, str | None, str | None]:
        """Authentifie un utilisateur via username/password (Resource Owner Password Credentials).

        Args:
            username: Le nom d'utilisateur ou l'email
            password: Le mot de passe

        Returns:
            Tuple contenant (UserContext, access_token, refresh_token, id_token)

        Raises:
            HTTPException: Si les identifiants sont invalides

        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                self.token_endpoint,
                data={
                    "grant_type": "password",
                    "client_id": settings.keycloak_client_id,
                    "client_secret": settings.keycloak_client_secret,
                    "username": username,
                    "password": password,
                    "scope": "openid profile email",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if response.status_code != status.HTTP_200_OK:
            error_data = response.json()
            error_description = error_data.get("error_description", "Invalid credentials")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_description,
            )

        tokens = response.json()
        claims = await self.decode_token(tokens["access_token"])
        user_context = LightWeightUserContext(claims=claims)

        return (
            user_context,
            tokens["access_token"],
            tokens.get("refresh_token"),
            tokens.get("id_token"),
        )

    # --------------------------------------------------------------------------
    # Keycloak Admin API Helpers
    # --------------------------------------------------------------------------

    async def _get_admin_token(self) -> str:
        """Obtient un token admin via le service account (client_credentials).

        Returns:
            Le token d'accès admin

        Raises:
            HTTPException: Si l'obtention du token échoue

        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_response = await client.post(
                self.token_endpoint,
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.keycloak_client_id,
                    "client_secret": settings.keycloak_client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if token_response.status_code != status.HTTP_200_OK:
            logger.error("Failed to get admin token: %s", token_response.text)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to connect to identity provider",
            )

        return token_response.json()["access_token"]

    async def _get_keycloak_user_id(self, admin_token: str, subject: str) -> str:
        """Récupère l'ID Keycloak d'un utilisateur via son subject (sub).

        Args:
            admin_token: Token admin pour l'API
            subject: Le subject (sub) du JWT de l'utilisateur

        Returns:
            L'ID Keycloak de l'utilisateur

        Raises:
            HTTPException: Si l'utilisateur n'est pas trouvé

        """
        admin_url = f"{settings.keycloak_url}/admin/realms/{settings.keycloak_realm}/users/{subject}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                admin_url,
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        if response.status_code != status.HTTP_200_OK:
            logger.error("Failed to get Keycloak user %s: %s", subject, response.text)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur non trouve dans Keycloak",
            )

        return response.json()["id"]

    # --------------------------------------------------------------------------
    # Keycloak Admin API Operations
    # --------------------------------------------------------------------------

    async def register_user(
        self,
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        username: str,
    ) -> None:
        """Crée un utilisateur dans Keycloak via l'Admin REST API.

        Utilise le service account du client pour obtenir un token admin,
        puis crée l'utilisateur dans le realm.

        Args:
            email: Adresse email
            password: Mot de passe
            first_name: Prénom
            last_name: Nom de famille
            username: Nom d'utilisateur

        Raises:
            HTTPException: Si la création échoue (email/username déjà pris, etc.)

        """
        admin_token = await self._get_admin_token()

        admin_url = f"{settings.keycloak_url}/admin/realms/{settings.keycloak_realm}/users"

        user_payload = {
            "username": username,
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "enabled": True,
            "emailVerified": True,
            "credentials": [
                {
                    "type": "password",
                    "value": password,
                    "temporary": False,
                },
            ],
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            create_response = await client.post(
                admin_url,
                json=user_payload,
                headers={
                    "Authorization": f"Bearer {admin_token}",
                    "Content-Type": "application/json",
                },
            )

        if create_response.status_code == 409:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Un utilisateur avec cet email ou ce nom d'utilisateur existe deja",
            )

        if create_response.status_code not in (201, 204):
            logger.error("Failed to create user in Keycloak: %s", create_response.text)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Erreur lors de la creation du compte",
            )

    async def update_user_profile(
        self,
        *,
        subject: str,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
    ) -> None:
        """Met à jour le profil d'un utilisateur dans Keycloak.

        Args:
            subject: Le subject (sub) JWT de l'utilisateur
            first_name: Nouveau prénom (optionnel)
            last_name: Nouveau nom (optionnel)
            email: Nouvel email (optionnel)

        Raises:
            HTTPException: Si la mise à jour échoue

        """
        admin_token = await self._get_admin_token()
        keycloak_id = await self._get_keycloak_user_id(admin_token, subject)

        # Construire le payload avec uniquement les champs fournis
        payload: dict[str, Any] = {}
        if first_name is not None:
            payload["firstName"] = first_name
        if last_name is not None:
            payload["lastName"] = last_name
        if email is not None:
            payload["email"] = email
            payload["emailVerified"] = True

        if not payload:
            return  # Rien à mettre à jour

        admin_url = f"{settings.keycloak_url}/admin/realms/{settings.keycloak_realm}/users/{keycloak_id}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.put(
                admin_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {admin_token}",
                    "Content-Type": "application/json",
                },
            )

        if response.status_code == 409:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Un utilisateur avec cet email existe deja",
            )

        if response.status_code not in (200, 204):
            logger.error("Failed to update user profile in Keycloak: %s", response.text)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Erreur lors de la mise a jour du profil",
            )

    async def change_user_password(
        self,
        *,
        subject: str,
        username: str,
        current_password: str,
        new_password: str,
    ) -> None:
        """Change le mot de passe d'un utilisateur dans Keycloak.

        Vérifie d'abord l'ancien mot de passe puis applique le nouveau.

        Args:
            subject: Le subject (sub) JWT de l'utilisateur
            username: Le nom d'utilisateur (pour vérifier l'ancien mdp)
            current_password: Mot de passe actuel
            new_password: Nouveau mot de passe

        Raises:
            HTTPException: Si l'ancien mdp est incorrect ou si la mise à jour échoue

        """
        # 1. Vérifier l'ancien mot de passe
        try:
            await self.authenticate_with_password(
                username=username,
                password=current_password,
            )
        except HTTPException:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Mot de passe actuel incorrect",
            )

        # 2. Changer le mot de passe via l'Admin API
        admin_token = await self._get_admin_token()
        keycloak_id = await self._get_keycloak_user_id(admin_token, subject)

        admin_url = (
            f"{settings.keycloak_url}/admin/realms/{settings.keycloak_realm}"
            f"/users/{keycloak_id}/reset-password"
        )

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.put(
                admin_url,
                json={
                    "type": "password",
                    "value": new_password,
                    "temporary": False,
                },
                headers={
                    "Authorization": f"Bearer {admin_token}",
                    "Content-Type": "application/json",
                },
            )

        if response.status_code not in (200, 204):
            logger.error("Failed to change password in Keycloak: %s", response.text)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Erreur lors du changement de mot de passe",
            )

    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        """Rafraîchit un access token à partir d'un refresh token.

        Args:
            refresh_token: Le refresh token

        Returns:
            Nouveaux tokens

        Raises:
            HTTPException: Si le rafraîchissement échoue

        """
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                self.token_endpoint,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": settings.keycloak_client_id,
                    "client_secret": settings.keycloak_client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if response.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=response.json(),
            )

        return TokenResponse(**response.json())

    # --------------------------------------------------------------------------
    # Token Extraction
    # --------------------------------------------------------------------------

    @staticmethod
    def extract_token(request: Request) -> str | None:
        """Extrait le JWT depuis l'Authorization header ou le cookie.

        Priorité donnée à l'Authorization header.

        Args:
            request: La requête HTTP

        Returns:
            Le token JWT ou None si absent

        """
        # 1. Essayer l'Authorization header (Bearer token)
        auth_header = request.headers.get("Authorization")
        if auth_header:
            scheme, param = get_authorization_scheme_param(auth_header)
            if scheme and scheme.lower() == "bearer" and param:
                return param

        # 2. Essayer le cookie
        return request.cookies.get("access_token")

    # --------------------------------------------------------------------------
    # User Context
    # --------------------------------------------------------------------------

    async def get_current_user(
        self,
        request: Request,
        response: Response,
    ) -> UserContext:
        """Récupère le contexte de l'utilisateur authentifié.

        Args:
            request: La requête HTTP
            response: La réponse HTTP (pour mettre à jour les cookies)

        Returns:
            Le contexte utilisateur

        Raises:
            HTTPException: Si l'utilisateur n'est pas authentifié

        """
        token = self.extract_token(request)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="not_authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )

        claims = await self.decode_token(token)
        return UserContext(claims=claims, token=token)

    async def get_current_user_optional(
        self,
        request: Request,
        response: Response,
    ) -> UserContext | None:
        """Récupère le contexte utilisateur si authentifié, sinon None.

        Args:
            request: La requête HTTP
            response: La réponse HTTP

        Returns:
            Le contexte utilisateur ou None

        """
        token = self.extract_token(request)
        if not token:
            return None

        try:
            return await self.get_current_user(request, response)
        except HTTPException:
            return None

    @staticmethod
    def _set_auth_cookies(
        response: Response,
        access_token: str,
        refresh_token: str,
    ) -> None:
        """Configure les cookies d'authentification."""
        cookie_config = {
            "httponly": True,
            "secure": settings.environment == "production",
            "samesite": "lax",
        }

        response.set_cookie("access_token", access_token, **cookie_config)
        response.set_cookie("refresh_token", refresh_token, **cookie_config)


# ==============================================================================
# Dependencies
# ==============================================================================


def get_security_service() -> SecurityService:
    """Dependency pour obtenir le service de sécurité."""
    return SecurityService()


async def require_user(
    request: Request,
    response: Response,
    security: Annotated[SecurityService, Depends(get_security_service)],
) -> UserContext:
    """Dependency FastAPI qui requiert un utilisateur authentifié.

    Usage:
        @router.get("/protected")
        async def protected_route(
            user: Annotated[UserContext, Depends(require_user)]
        ):
            return {"user_id": user.subject}
    """
    return await security.get_current_user(request, response)


async def optional_user(
    request: Request,
    response: Response,
    security: Annotated[SecurityService, Depends(get_security_service)],
) -> UserContext | None:
    """Dependency FastAPI pour un utilisateur optionnel.

    Usage:
        @router.get("/public")
        async def public_route(
            user: Annotated[UserContext | None, Depends(optional_user)]
        ):
            if user:
                return {"user_id": user.subject}
            return {"message": "Anonymous user"}
    """
    return await security.get_current_user_optional(request, response)


def require_roles(*expected_roles: str) -> UserContext:
    """Créer une dependency qui vérifie les rôles.

    Args:
        *expected_roles: Les rôles requis (OR logique)

    Usage:
        @router.get("/admin")
        async def admin_route(
            user: Annotated[UserContext, Depends(require_roles("admin", "superuser"))]
        ):
            return {"message": "Welcome admin"}

    """
    expected_roles_set = set(expected_roles)

    async def dependency(
        request: Request,
        response: Response,
        security: Annotated[SecurityService, Depends(get_security_service)],
    ) -> UserContext:
        user = await security.get_current_user(request, response)
        if not set(user.roles).intersection(expected_roles_set):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return dependency
