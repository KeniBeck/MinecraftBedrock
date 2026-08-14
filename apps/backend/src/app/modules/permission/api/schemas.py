"""Schemas HTTP del módulo Permission (vertical slice §16)."""

from __future__ import annotations

from pydantic import BaseModel


class AllowlistEntryResponse(BaseModel):
    name: str
    xuid: str
    ignores_player_limit: bool = False


class AllowlistAddRequest(BaseModel):
    name: str
    xuid: str
    ignores_player_limit: bool = False


class SetAllowlistEnabledRequest(BaseModel):
    enabled: bool


class PermissionEntryResponse(BaseModel):
    xuid: str
    level: str


class OperatorResponse(BaseModel):
    xuid: str
    level: str


class SetPermissionRequest(BaseModel):
    level: str
