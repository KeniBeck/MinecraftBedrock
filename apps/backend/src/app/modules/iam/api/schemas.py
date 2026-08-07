"""Schemas HTTP del módulo IAM (vertical slice §16 ``modules/iam/api``).

Los DTOs de entrada/salida son de presentación: no exponen hashes ni internos
del dominio; los comandos/results de ``application`` son los que se traducen.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RoleName = Literal["super_admin", "admin", "operator", "viewer"]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=256)
    display_name: str = Field(default="", max_length=128)


class AssignRoleRequest(BaseModel):
    role: RoleName


class AssignMembershipRequest(BaseModel):
    server_id: str = Field(min_length=1)
    role: RoleName


class IdentityResponse(BaseModel):
    id: str
    username: str
    roles: list[str] = Field(default_factory=list)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    identity: IdentityResponse


class UserResponse(BaseModel):
    id: str
    username: str
    display_name: str
    status: str
    roles: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    last_login_at: datetime | None = None
