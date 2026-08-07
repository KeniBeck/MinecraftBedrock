"""Routers HTTP del módulo IAM (vertical slice §16 ``modules/iam/api``).

Endpoints de autenticación (login/refresh/logout) y gestión de usuarios, roles
globales y membresías. Las operaciones de gestión exigen admin global
(recurso ``None``) vía ``require_action``; la autenticación usa la facade
IamFacade. La API no contiene reglas de negocio (Blueprint §4.7).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.bootstrap.security import get_container, require_action
from app.kernel.ports.access import Identity
from app.modules.iam.api.schemas import (
    AssignMembershipRequest,
    AssignRoleRequest,
    CreateUserRequest,
    IdentityResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from app.modules.iam.application.commands import (
    AssignMembershipCommand,
    AssignRoleCommand,
    CreateUserCommand,
    LoginCommand,
    LogoutCommand,
    RefreshCommand,
)
from app.modules.iam.application.facade import IamFacade
from app.modules.iam.application.results import AuthResult, UserView
from app.modules.iam.domain.role import BuiltinRole

router = APIRouter(tags=["iam"])


def _facade(request: Request) -> IamFacade:
    return get_container(request).iam_facade


def _token_response(result: AuthResult) -> TokenResponse:
    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        expires_in=result.expires_in,
        identity=IdentityResponse(
            id=result.identity.id,
            username=result.identity.username,
            roles=list(result.identity.roles),
        ),
    )


def _user_response(view: UserView) -> UserResponse:
    return UserResponse(
        id=view.id,
        username=view.username,
        display_name=view.display_name,
        status=view.status,
        roles=list(view.roles),
        created_at=view.created_at,
        last_login_at=view.last_login_at,
    )


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/auth/login", response_model=TokenResponse, summary="Inicio de sesión")
async def login(body: LoginRequest, request: Request) -> TokenResponse:
    result = await _facade(request).login(
        LoginCommand(
            username=body.username,
            password=body.password,
            ip=_client_ip(request),
            ua=request.headers.get("user-agent"),
        )
    )
    return _token_response(result)


@router.post("/auth/refresh", response_model=TokenResponse, summary="Rotar tokens")
async def refresh(body: RefreshRequest, request: Request) -> TokenResponse:
    result = await _facade(request).refresh(
        RefreshCommand(
            refresh_token=body.refresh_token,
            ip=_client_ip(request),
            ua=request.headers.get("user-agent"),
        )
    )
    return _token_response(result)


@router.post("/auth/logout", status_code=204, summary="Cerrar sesión")
async def logout(body: LogoutRequest, request: Request) -> None:
    await _facade(request).logout(LogoutCommand(refresh_token=body.refresh_token))


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=201,
    summary="Crear usuario (admin)",
)
async def create_user(
    body: CreateUserRequest,
    request: Request,
    identity: Identity = Depends(require_action("iam.user.create")),
) -> UserResponse:
    view = await _facade(request).create_user(
        CreateUserCommand(
            username=body.username,
            password=body.password,
            display_name=body.display_name,
            actor_id=identity.id,
        )
    )
    return _user_response(view)


@router.post(
    "/users/{user_id}/roles",
    response_model=UserResponse,
    summary="Asignar rol global (admin)",
)
async def assign_role(
    user_id: str,
    body: AssignRoleRequest,
    request: Request,
    identity: Identity = Depends(require_action("iam.user.role.assign")),
) -> UserResponse:
    view = await _facade(request).assign_role(
        AssignRoleCommand(
            user_id=user_id,
            role=BuiltinRole(body.role),
            actor_id=identity.id,
        )
    )
    return _user_response(view)


@router.post(
    "/users/{user_id}/memberships",
    status_code=204,
    summary="Asignar membresía por servidor (admin)",
)
async def assign_membership(
    user_id: str,
    body: AssignMembershipRequest,
    request: Request,
    identity: Identity = Depends(require_action("iam.user.membership.assign")),
) -> None:
    await _facade(request).assign_membership(
        AssignMembershipCommand(
            user_id=user_id,
            server_id=body.server_id,
            role=BuiltinRole(body.role),
            actor_id=identity.id,
        )
    )
