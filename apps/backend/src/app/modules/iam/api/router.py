"""Routers HTTP del módulo IAM (vertical slice §16 ``modules/iam/api``).

Endpoints de autenticación (login/refresh/logout), 2FA (TOTP), API keys y
gestión de usuarios, roles globales y membresías. Las operaciones de gestión
exigen admin global (recurso ``None``) vía ``require_action``; la
autenticación usa la facade IamFacade. La API no contiene reglas de negocio
(Blueprint §4.7).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request

from app.bootstrap.security import get_container, get_current_user, require_action
from app.kernel.ports.access import Identity
from app.modules.iam.api.schemas import (
    ApiKeyCreatedResponse,
    ApiKeyRequest,
    ApiKeyResponse,
    AssignMembershipRequest,
    AssignRoleRequest,
    AuditLogListResponse,
    AuditLogResponse,
    AuditVerifyResponse,
    BackupCodesResponse,
    ConfirmTwoFactorRequest,
    CreateUserRequest,
    EnableTwoFactorResponse,
    IdentityResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    RoleResponse,
    TokenResponse,
    UpdateUserRequest,
    UserResponse,
    VerifyTwoFactorLoginRequest,
)
from app.modules.iam.application.commands import (
    AssignMembershipCommand,
    AssignRoleCommand,
    ConfirmTwoFactorCommand,
    CreateApiKeyCommand,
    CreateUserCommand,
    DeleteUserCommand,
    EnableTwoFactorCommand,
    LoginCommand,
    LogoutCommand,
    RefreshCommand,
    RegenerateBackupCodesCommand,
    RevokeApiKeyCommand,
    RotateApiKeyCommand,
    UpdateUserCommand,
    VerifyTwoFactorLoginCommand,
)
from app.modules.iam.application.facade import IamFacade
from app.modules.iam.application.results import ApiKeyCreated, AuditLogView, AuthResult, UserView
from app.modules.iam.domain.errors import TwoFactorRequiredError
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


def _login_response(result: AuthResult) -> LoginResponse:
    token = _token_response(result)
    return LoginResponse(
        requires_2fa=False,
        temp_token=None,
        access_token=token.access_token,
        refresh_token=token.refresh_token,
        expires_in=token.expires_in,
        identity=token.identity,
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
        email=view.email,
    )


def _audit_log_response(view: AuditLogView) -> AuditLogResponse:
    return AuditLogResponse(
        id=view.id,
        actor_id=view.actor_id,
        actor_type=view.actor_type,
        action=view.action,
        resource_type=view.resource_type,
        resource_id=view.resource_id,
        result=view.result,
        detail=view.detail,
        ip=view.ip,
        ua=view.ua,
        created_at=view.created_at,
        hash=view.hash,
        prev_hash=view.prev_hash,
    )


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/auth/login", response_model=LoginResponse, summary="Inicio de sesión")
async def login(body: LoginRequest, request: Request) -> LoginResponse:
    try:
        result = await _facade(request).login(
            LoginCommand(
                username=body.username,
                password=body.password,
                ip=_client_ip(request),
                ua=request.headers.get("user-agent"),
            )
        )
    except TwoFactorRequiredError as exc:
        context = exc.context or {}
        temp_token = str(context.get("temp_token", ""))
        return LoginResponse(requires_2fa=True, temp_token=temp_token)
    return _login_response(result)


@router.post(
    "/auth/verify-2fa",
    response_model=TokenResponse,
    summary="Completar login con el segundo factor",
)
async def verify_two_factor_login(
    body: VerifyTwoFactorLoginRequest, request: Request
) -> TokenResponse:
    result = await _facade(request).verify_two_factor_login(
        VerifyTwoFactorLoginCommand(
            temp_token=body.temp_token,
            code=body.code,
            ip=_client_ip(request),
            ua=request.headers.get("user-agent"),
        )
    )
    return _token_response(result)


@router.post(
    "/auth/2fa/enable",
    response_model=EnableTwoFactorResponse,
    summary="Iniciar 2FA (genera secreto + backup codes)",
)
async def enable_two_factor(
    request: Request,
    identity: Identity = Depends(get_current_user),
) -> EnableTwoFactorResponse:
    result = await _facade(request).enable_two_factor(EnableTwoFactorCommand(user_id=identity.id))
    return EnableTwoFactorResponse(
        secret=result.secret,
        provisioning_uri=result.provisioning_uri,
        backup_codes=list(result.backup_codes),
    )


@router.post(
    "/auth/2fa/verify",
    status_code=204,
    summary="Confirmar 2FA (validar código TOTP)",
)
async def confirm_two_factor(
    body: ConfirmTwoFactorRequest,
    request: Request,
    identity: Identity = Depends(get_current_user),
) -> None:
    await _facade(request).confirm_two_factor(
        ConfirmTwoFactorCommand(user_id=identity.id, code=body.code)
    )


@router.post(
    "/auth/2fa/backup",
    response_model=BackupCodesResponse,
    summary="Regenerar backup codes (2FA ya verificado)",
)
async def regenerate_backup_codes(
    request: Request,
    identity: Identity = Depends(get_current_user),
) -> BackupCodesResponse:
    codes = await _facade(request).regenerate_backup_codes(
        RegenerateBackupCodesCommand(user_id=identity.id)
    )
    return BackupCodesResponse(backup_codes=list(codes))


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


@router.get(
    "/users",
    response_model=list[UserResponse],
    summary="Listar usuarios (get: iam.view)",
)
async def list_users(
    request: Request,
    identity: Identity = Depends(require_action("iam.view")),
) -> list[UserResponse]:
    views = await _facade(request).list_users()
    del identity
    return [_user_response(view) for view in views]


@router.get(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Detalle de un usuario (get: iam.view)",
)
async def get_user(
    user_id: str,
    request: Request,
    identity: Identity = Depends(require_action("iam.view")),
) -> UserResponse:
    view = await _facade(request).get_user(user_id)
    del identity
    return _user_response(view)


@router.put(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Actualizar usuario (display_name, email, status, roles; iam.manage)",
)
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    request: Request,
    identity: Identity = Depends(require_action("iam.manage")),
) -> UserResponse:
    roles = (
        tuple(BuiltinRole(role) for role in body.roles)
        if body.roles is not None
        else None
    )
    view = await _facade(request).update_user(
        UpdateUserCommand(
            user_id=user_id,
            display_name=body.display_name,
            email=body.email,
            status=body.status,
            roles=roles,
            actor_id=identity.id,
        )
    )
    return _user_response(view)


@router.delete(
    "/users/{user_id}",
    status_code=204,
    summary="Suspender usuario (soft delete; iam.manage)",
)
async def delete_user(
    user_id: str,
    request: Request,
    identity: Identity = Depends(require_action("iam.manage")),
) -> None:
    await _facade(request).delete_user(
        DeleteUserCommand(user_id=user_id, actor_id=identity.id)
    )


@router.get(
    "/roles",
    response_model=list[RoleResponse],
    summary="Catálogo de roles del panel (get: iam.view)",
)
async def list_roles(
    request: Request,
    identity: Identity = Depends(require_action("iam.view")),
) -> list[RoleResponse]:
    views = await _facade(request).list_roles()
    del identity
    return [
        RoleResponse(
            id=view.id,
            name=view.name,
            description=view.description,
            is_system=view.is_system,
        )
        for view in views
    ]


# -- API keys (Fase H paso 18) -------------------------------------------------


@router.get(
    "/iam/api-keys",
    response_model=list[ApiKeyResponse],
    summary="Listar API keys del usuario (admin)",
)
async def list_api_keys(
    request: Request,
    identity: Identity = Depends(require_action("iam.apikey.manage")),
) -> list[ApiKeyResponse]:
    keys = await _facade(request).list_api_keys(identity.id)
    return [
        ApiKeyResponse(
            id=key.id,
            name=key.name,
            scopes=list(key.scopes),
            created_at=key.created_at,
            last_used_at=key.last_used_at,
            expires_at=key.expires_at,
        )
        for key in keys
    ]


@router.post(
    "/iam/api-keys",
    response_model=ApiKeyCreatedResponse,
    status_code=201,
    summary="Crear API key (admin; material visible una vez)",
)
async def create_api_key(
    body: ApiKeyRequest,
    request: Request,
    identity: Identity = Depends(require_action("iam.apikey.create")),
) -> ApiKeyCreatedResponse:
    created = await _facade(request).create_api_key(
        CreateApiKeyCommand(user_id=identity.id, name=body.name, scopes=tuple(body.scopes))
    )
    return _api_key_created_response(created)


@router.delete(
    "/iam/api-keys/{key_id}",
    status_code=204,
    summary="Revocar API key (admin)",
)
async def revoke_api_key(
    key_id: str,
    request: Request,
    identity: Identity = Depends(require_action("iam.apikey.manage")),
) -> None:
    await _facade(request).revoke_api_key(RevokeApiKeyCommand(user_id=identity.id, key_id=key_id))


@router.post(
    "/iam/api-keys/{key_id}/regenerate",
    response_model=ApiKeyCreatedResponse,
    summary="Rotar API key (admin; material visible una vez)",
)
async def rotate_api_key(
    key_id: str,
    request: Request,
    identity: Identity = Depends(require_action("iam.apikey.manage")),
) -> ApiKeyCreatedResponse:
    created = await _facade(request).rotate_api_key(
        RotateApiKeyCommand(user_id=identity.id, key_id=key_id)
    )
    return _api_key_created_response(created)


# -- auditoría tamper-evident (Fase H paso 18) -----------------------------------


@router.get(
    "/iam/audit/verify",
    response_model=AuditVerifyResponse,
    summary="Verificar integridad del audit log (admin)",
)
async def verify_audit(
    request: Request,
    identity: Identity = Depends(require_action("iam.audit.view")),
) -> AuditVerifyResponse:
    del identity
    errors = await _facade(request).verify_audit()
    return AuditVerifyResponse(valid=not errors, errors=errors)


@router.get(
    "/iam/audit",
    response_model=AuditLogListResponse,
    summary="Listar audit log con filtros y paginación (get: iam.view)",
)
async def list_audit_logs(
    request: Request,
    identity: Identity = Depends(require_action("iam.view")),
    actor_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> AuditLogListResponse:
    page = await _facade(request).list_audit_logs(
        actor_id=actor_id,
        action=action,
        from_at=from_at,
        to_at=to_at,
        limit=limit,
        offset=offset,
    )
    del identity
    return AuditLogListResponse(
        items=[_audit_log_response(view) for view in page.items],
        total=page.total,
    )


def _api_key_created_response(created: ApiKeyCreated) -> ApiKeyCreatedResponse:
    return ApiKeyCreatedResponse(
        id=created.key.id,
        name=created.key.name,
        scopes=list(created.key.scopes),
        created_at=created.key.created_at,
        last_used_at=created.key.last_used_at,
        expires_at=created.key.expires_at,
        material=created.material,
    )
