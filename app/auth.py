"""
Internal Service Authentication Middleware

Protects all Analyzer endpoints so that ONLY the Talent Backend
can access them. The Backend sends a shared secret token in the
X-Internal-Service-Token header on every request.

Security model:
  - The token is a shared secret stored in environment variables
  - It is NEVER exposed in responses, logs, or error messages
  - Missing or invalid token returns a generic 401 Unauthorized
  - The Analyzer does NOT implement user JWT auth — that is
    the Backend's responsibility
"""

import os
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response


# Paths that are exempt from internal auth (health checks, docs)
EXEMPT_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}


class InternalServiceAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware that validates the X-Internal-Service-Token header
    on every request. If the token is missing or invalid, the
    request is rejected with 401 Unauthorized.
    """

    def __init__(self, app, token: str):
        super().__init__(app)
        if not token:
            raise ValueError(
                "INTERNAL_SERVICE_TOKEN must be set in environment variables"
            )
        self._token = token

    async def dispatch(self, request: Request, call_next):
        # Skip auth for exempt paths
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        # Extract token from header
        provided_token = request.headers.get("X-Internal-Service-Token")

        # Validate — constant-time comparison to prevent timing attacks
        if not provided_token or not _constant_time_compare(provided_token, self._token):
            # Return generic error — never reveal WHY it failed
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized"},
            )

        # Token valid — pass request through
        return await call_next(request)


def _constant_time_compare(a: str, b: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks."""
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a, b):
        result |= ord(x) ^ ord(y)
    return result == 0


def get_internal_token() -> str:
    """
    Load the internal service token from environment variables.
    Raises ValueError if not configured (fail fast on startup).
    """
    token = os.environ.get("INTERNAL_SERVICE_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "INTERNAL_SERVICE_TOKEN environment variable is required. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    return token
