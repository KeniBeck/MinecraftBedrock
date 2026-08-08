"""Mapeo central de errores de dominio → HTTP (Blueprint §4.7, §11.1).

Único punto de traducción para los tres módulos: la API nunca decide el status
code. Se registran handlers en la aplicación FastAPI para ``AppError``
(arboles de dominio/infraestructura), ``RequestValidationError`` (Pydantic) y
``Exception`` (catch-all, correla el request). El cuerpo es consistente:

    {"detail": {"code", "message", "context"}}

La autenticación/autorización de presentación (``bootstrap/security.py``)
reusa ``http_error`` para emitir la misma forma.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.kernel.errors import (
    AppError,
    BusinessRuleViolation,
    ConcurrencyConflictError,
    ConsoleError,
    HttpError,
    InfrastructureError,
    InvalidStateError,
    NotFoundError,
    UnexpectedError,
    ValidationError,
)
from app.modules.console.domain.errors import CommandRejectedError
from app.modules.iam.domain.errors import (
    AccountSuspendedError,
    ApiKeyInvalidError,
    ApiKeyScopeError,
    AuthenticationError,
    AuthorizationError,
    ForbiddenError,
    InvalidCredentialsError,
    RoleNotFoundError,
    SessionNotFoundError,
    TokenExpiredError,
    TokenInvalidError,
    TokenRevokedError,
    TwoFactorInvalidError,
    TwoFactorNotEnabledError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.modules.server.domain.errors import (
    ServerNotFoundError,
    ServerNotMaterializedError,
    ServerPortExhaustedError,
    ServerStateError,
)

_AUTH_FAILURES = (
    InvalidCredentialsError,
    TokenExpiredError,
    TokenInvalidError,
    TokenRevokedError,
)


def status_for(error: AppError) -> int:
    """Traduce un ``AppError`` a status HTTP (mapping central y único)."""
    if isinstance(error, HttpError):
        return error.status_code
    if isinstance(
        error,
        _AUTH_FAILURES + (AuthenticationError, ApiKeyInvalidError, TwoFactorInvalidError),
    ):
        return 401
    if isinstance(
        error,
        (AccountSuspendedError, AuthorizationError, ForbiddenError, ApiKeyScopeError),
    ):
        return 403
    if isinstance(
        error,
        (
            UserNotFoundError,
            RoleNotFoundError,
            SessionNotFoundError,
            ServerNotFoundError,
            NotFoundError,
        ),
    ):
        return 404
    if isinstance(error, (CommandRejectedError, ValidationError)):
        return 422
    if isinstance(
        error,
        (
            UserAlreadyExistsError,
            ConcurrencyConflictError,
            InvalidStateError,
            ServerStateError,
            ServerNotMaterializedError,
            ServerPortExhaustedError,
            BusinessRuleViolation,
            ConsoleError,
            TwoFactorNotEnabledError,
        ),
    ):
        return 409
    if isinstance(error, InfrastructureError):
        return 503
    if isinstance(error, UnexpectedError):
        return 500
    return 500


def http_error(
    status_code: int,
    code: str,
    message: str,
    context: dict[str, Any] | None = None,
) -> HttpError:
    """Construye un ``HttpError`` con la forma de respuesta consistente."""
    return HttpError(message, status_code=status_code, code=code, context=context)


def _body(code: str, message: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"detail": {"code": code, "message": message, "context": context or {}}}


def register_exception_handlers(app: FastAPI) -> None:
    """Registra los handlers de errores de la aplicación FastAPI."""

    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=status_for(exc),
            content=_body(exc.code, exc.message, exc.context),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        del request
        errors = [{"loc": list(e.get("loc", [])), "msg": e.get("msg", "")} for e in exc.errors()]
        return JSONResponse(
            status_code=422,
            content=_body(
                "HTTP.VALIDATION_ERROR",
                "La petición no cumple el contrato del endpoint",
                {"errors": errors},
            ),
        )

    @app.exception_handler(Exception)
    async def _unexpected_handler(request: Request, exc: Exception) -> JSONResponse:
        del request, exc
        return JSONResponse(
            status_code=500,
            content=_body("KERNEL.UNEXPECTED", "Error interno inesperado"),
        )
