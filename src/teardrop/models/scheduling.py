"""Schedule and event-trigger models."""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


def _validate_https_callback_url(value: str | None) -> str | None:
    if value is None:
        return value

    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("callback_url must be an absolute https URL")
    return value


class ScheduledRun(BaseModel):
    id: str
    org_id: str
    user_id: str
    name: str
    prompt: str
    schedule_kind: Literal["interval"]
    interval_seconds: int
    enabled: bool
    callback_url: str | None = None
    next_run_at: str | None
    last_run_at: str | None = None
    consecutive_failures: int
    created_at: str
    updated_at: str

    model_config = {"extra": "allow"}


ScheduledRunItem = ScheduledRun


class ScheduledRunListResponse(BaseModel):
    """Response from GET /agent/schedules."""

    items: list[ScheduledRun]
    next_cursor: str | None = None


class ScheduledRunResult(BaseModel):
    id: str
    schedule_id: str
    org_id: str
    run_id: str
    status: str
    output_text: str = ""
    cost_usdc: int
    error: str = ""
    created_at: str

    model_config = {"extra": "allow"}


ScheduledRunResultItem = ScheduledRunResult


class ScheduledRunsPage(BaseModel):
    items: list[ScheduledRunResult] = Field(default_factory=list)
    next_cursor: str | None = None


class ScheduledRunResultsResponse(BaseModel):
    """Alias matching OpenAPI schema for schedule/trigger run lists."""

    items: list[ScheduledRunResult]
    next_cursor: str | None = None


class CreateScheduleRequest(BaseModel):
    name: str
    prompt: str
    interval_seconds: int = Field(ge=1)
    callback_url: str | None = None

    @field_validator("callback_url")
    @classmethod
    def _validate_callback_url(cls, value: str | None) -> str | None:
        return _validate_https_callback_url(value)


class UpdateScheduleRequest(BaseModel):
    name: str | None = None
    prompt: str | None = None
    interval_seconds: int | None = Field(default=None, ge=1)
    enabled: bool | None = None
    callback_url: str | None = None

    @field_validator("callback_url")
    @classmethod
    def _validate_callback_url(cls, value: str | None) -> str | None:
        return _validate_https_callback_url(value)


class EventTrigger(BaseModel):
    id: str
    org_id: str
    user_id: str
    name: str
    prompt: str
    schedule_kind: Literal["event"]
    enabled: bool
    callback_url: str | None = None
    trigger_token: str | None = None
    event_path: str | None = None
    consecutive_failures: int
    last_run_at: str | None = None
    created_at: str
    updated_at: str

    model_config = {"extra": "allow"}


EventTriggerItem = EventTrigger


class EventTriggerListResponse(BaseModel):
    """Response from GET /agent/event-triggers."""

    items: list[EventTrigger]
    next_cursor: str | None = None


class EventTriggerWithSecret(EventTrigger):
    secret: str


class EventTriggerCreatedResponse(EventTriggerWithSecret):
    """Response from POST /agent/event-triggers."""


class CreateEventTriggerRequest(BaseModel):
    name: str
    prompt: str
    callback_url: str | None = None

    @field_validator("callback_url")
    @classmethod
    def _validate_callback_url(cls, value: str | None) -> str | None:
        return _validate_https_callback_url(value)


class UpdateEventTriggerRequest(BaseModel):
    name: str | None = None
    prompt: str | None = None
    enabled: bool | None = None
    callback_url: str | None = None

    @field_validator("callback_url")
    @classmethod
    def _validate_callback_url(cls, value: str | None) -> str | None:
        return _validate_https_callback_url(value)


class ScheduleDeletedResponse(BaseModel):
    """Response from DELETE /agent/schedules/{schedule_id}."""

    id: str = ""
    status: str
    deleted_at: str = ""

    model_config = {"extra": "allow"}


class RotateSecretResponse(BaseModel):
    """Response from POST /agent/event-triggers/{schedule_id}/rotate-secret."""

    id: str
    secret: str
    rotated_at: str = ""

    model_config = {"extra": "allow"}
