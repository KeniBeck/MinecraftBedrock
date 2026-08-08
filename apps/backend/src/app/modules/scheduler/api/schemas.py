"""Schemas HTTP del módulo Scheduler (vertical slice §16 ``modules/scheduler/api``)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreateTaskRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: str
    cron: str
    payload: dict[str, Any] = Field(default_factory=dict)
    max_retries: int = Field(default=3, ge=0)
    backoff_seconds: int = Field(default=60, ge=0)


class UpdateTaskRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    cron: str | None = None
    payload: dict[str, Any] | None = None
    max_retries: int | None = Field(default=None, ge=0)
    backoff_seconds: int | None = Field(default=None, ge=0)
    state: str | None = None


class ScheduleTaskResponse(BaseModel):
    id: str
    server_id: str
    name: str
    type: str
    cron: str
    payload: dict[str, Any]
    state: str
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_result: str | None
    failures: int
    max_retries: int
    backoff_seconds: int
    created_at: datetime | None
    updated_at: datetime | None
