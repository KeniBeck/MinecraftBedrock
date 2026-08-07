"""Schemas HTTP del módulo Player (vertical slice §16 ``modules/player/api``)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ResolvePlayerResponse(BaseModel):
    server_id: str
    name: str
    xuid: str


class PlayerResponse(BaseModel):
    xuid: str
    name: str
    first_seen_at: datetime
    last_seen_at: datetime
    playtime_seconds: int


class PlaySessionResponse(BaseModel):
    id: str
    server_id: str
    xuid: str
    joined_at: datetime
    left_at: datetime | None
    reason: str | None
    playtime_seconds: int


class CommandAckResponse(BaseModel):
    server_id: str
    command: str
    priority: str
    seq: int
    at: datetime
