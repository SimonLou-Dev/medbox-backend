# medbox/api/middlewares/auth_middleware.py


from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from medbox.core.services.security import SecurityService


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware de gestion de l'auth."""

    def __init__(self, app, security_service: SecurityService) -> None:
        """Constructeur."""
        super().__init__(app)
        self.security_service = security_service

    async def dispatch(self, request: Request, call_next) -> Response:
        """Fonction de vérification."""
        response = Response("Internal server error", status_code=500)

        # Étape 1 — Extraire le token
        token = SecurityService.extract_token(request)

        if not token:
            # Pas authentifié → request.state.user = None
            request.state.user = None
            return await call_next(request)

        # Étape 2 — Essayer de décoder / refresh
        try:
            user_ctx = await self.security_service.get_current_user(
                request,
                response,
            )
            request.state.user = user_ctx  # UserContext
        except Exception:
            request.state.user = None

        # Étape 3 — Continue
        return await call_next(request)
