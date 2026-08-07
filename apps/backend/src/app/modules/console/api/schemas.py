"""Schemas HTTP del módulo Console (vertical slice §16 ``modules/console/api``)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

PriorityName = Literal["critical", "high", "normal", "low"]


class SendCommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=512)
    priority: PriorityName = "normal"


class ConsoleLineResponse(BaseModel):
    seq: int
    server_id: str
    line: str


class BufferResponse(BaseModel):
    lines: list[ConsoleLineResponse]
    high_water_mark: int


class CommandAckResponse(BaseModel):
    server_id: str
    command: str
    priority: str
    seq: int
    at: datetime
