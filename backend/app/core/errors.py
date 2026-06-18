"""Domain errors mapped to HTTP responses at the API edge."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    status_code: int = 400
    code: str = "domain_error"


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"


class InvalidStateTransition(DomainError):
    status_code = 409
    code = "invalid_state_transition"


class ProviderError(DomainError):
    status_code = 502
    code = "provider_error"


class PayloadTooLarge(DomainError):
    status_code = 413
    code = "payload_too_large"


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(_req: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": str(exc) or exc.code}},
        )
