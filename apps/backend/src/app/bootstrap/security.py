"""Dependencias de autenticación/autorización compartidas (Blueprint §4.5, §5.1).

Se construyen una sola vez en ``bootstrap/`` y los tres módulos las reusan:

- ``get_current_user``: Bearer access token → ``Identity`` (decodifica el JWT
  vía ``IamFacade.resolve_access``; la autenticación por credenciales es
  ``AccessControlPort.authenticate`` usada en ``POST /auth/login``).
- ``require_action(action)``: autoriza una acción de panel (recurso ``None``),
  p. ej. crear usuario/servidor (admin global+).
- ``require_server_action(action)``: autoriza una acción sobre un servidor vía
  ``AccessControlPort.authorize`` (membresía por servidor).
- ``ws_identity``: resuelve la identidad en un handshake WebSocket (token por
  query o cabecera ``Authorization``), devolviendo ``None`` si es inválido.

Todas emiten errores con la misma forma que ``bootstrap/errors.py``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request, WebSocket
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.bootstrap.container import Container
from app.bootstrap.errors import http_error
from app.kernel.ports.access import Identity
from app.modules.iam.domain.errors import TokenExpiredError, TokenInvalidError, TokenRevokedError

_bearer = HTTPBearer(auto_error=False)

_AUTH_FAILURES = (TokenExpiredError, TokenInvalidError, TokenRevokedError)


def get_container(request: Request) -> Container:
    """Contenedor de dependencias instalado en ``app.state``."""
    container: Container = request.app.state.container
    return container


def resolve_access(token: str, container: Container) -> Identity:
    """Decodifica y valida el access token contra IAM."""
    return container.iam_facade.resolve_access(token)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> Identity:
    """Identidad autenticada: Bearer token o API key (``X-API-Key``)."""
    container = get_container(request)

    if credentials is not None and credentials.credentials:
        try:
            return resolve_access(credentials.credentials, container)
        except _AUTH_FAILURES as exc:
            raise http_error(401, exc.code, exc.message) from exc

    api_key = request.headers.get("x-api-key")
    if api_key:
        return await _resolve_api_key_identity(api_key, container)

    raise http_error(401, "AUTH.TOKEN_MISSING", "Falta el token de acceso")


async def _resolve_api_key_identity(raw: str, container: Container) -> Identity:
    """Resuelve la identidad desde el material de una API key (scopes incluidos).

    La key se autoriza por el usuario al que pertenece y sus scopes limitan las
    acciones (intersección en ``AccessControlService.authorize``).
    """
    from app.kernel.ports.access import Identity as KernelIdentity

    key = await container.iam_facade.resolve_api_key(raw)
    if key is None:
        raise http_error(401, "AUTH.API_KEY_INVALID", "API key inválida o vencida")
    user = await container.iam_facade.deps.repository.get(key.user_id)
    if user is None:
        raise http_error(401, "AUTH.API_KEY_INVALID", "Usuario de la API key no existe")
    return KernelIdentity(
        id=user.id,
        username=user.username,
        roles=tuple(sorted(role.value for role in user.roles)),
        scopes=key.scopes,
        is_api_key=True,
    )


def require_action(action: str) -> Callable[..., Awaitable[Identity]]:
    """Autoriza una acción de panel (recurso ``None``); admin global+.

    Uso: ``identity: Identity = Depends(require_action("iam.user.create"))``.
    """

    async def _dependency(
        request: Request,
        identity: Identity = Depends(get_current_user),  # noqa: B008
    ) -> Identity:
        decision = await get_container(request).iam_facade.access_control.authorize(
            identity, action, None
        )
        if not decision.allowed:
            raise http_error(
                403,
                "AUTH.FORBIDDEN",
                f"No autorizado para la acción {action}",
                {"reason": decision.reason},
            )
        return identity

    return _dependency


def require_server_action(action: str) -> Callable[..., Awaitable[Identity]]:
    """Autoriza una acción sobre un servidor (membresía vía ACL).

    Uso: ``identity: Identity = Depends(require_server_action("server.start"))``
    en un endpoint con parámetro de ruta ``server_id``.
    """

    async def _dependency(
        server_id: str,
        request: Request,
        identity: Identity = Depends(get_current_user),  # noqa: B008
    ) -> Identity:
        decision = await get_container(request).iam_facade.access_control.authorize(
            identity, action, server_id
        )
        if not decision.allowed:
            raise http_error(
                403,
                "AUTH.FORBIDDEN",
                f"No autorizado para {action} sobre el servidor {server_id}",
                {"server_id": server_id, "reason": decision.reason},
            )
        return identity

    return _dependency


def _bearer_from_header(value: str | None) -> str | None:
    if not value or not value.lower().startswith("bearer "):
        return None
    return value[7:].strip()


async def ws_identity(websocket: WebSocket, container: Container) -> Identity | None:
    """Resuelve la identidad en un handshake WebSocket (token por query/header).

    Devuelve ``None`` si falta el token o es inválido; el endpoint decide el
    código de cierre (ADR-002: authN en el handshake).
    """
    token = websocket.query_params.get("token") or _bearer_from_header(
        websocket.headers.get("authorization")
    )
    if not token:
        return None
    try:
        return resolve_access(token, container)
    except _AUTH_FAILURES:
        return None
