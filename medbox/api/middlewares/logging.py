# medbox/api/middlewares/request_logging_middleware.py

import logging
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware de logging des requêtes HTTP.

    Objectif:
    - Avoir une preuve fiable que les requêtes atteignent bien FastAPI
    - Logguer méthode, path, status, durée
    - Facultatif: logguer l'IP client (utile derrière Traefik)
    """

    def __init__(self, app) -> None:
        """Constructeur."""
        super().__init__(app)
        self.logger = logging.getLogger("medbox.http")

    async def dispatch(self, request: Request, call_next) -> Response:
        """Log la requête et la réponse."""
        start = time.perf_counter()

        response: Response = await call_next(request)

        duration_ms = int((time.perf_counter() - start) * 1000)

        # Si tu es derrière Traefik et que tu as bien les headers proxy,
        # tu peux essayer de récupérer l'IP réelle via X-Forwarded-For.
        forwarded_for = request.headers.get("x-forwarded-for")
        real_ip = (
            forwarded_for.split(",")[0].strip()
            if forwarded_for
            else request.client.host
        )

        self.logger.info(
            "%s %s -> %s (%sms) ip=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            real_ip,
        )

        return response
