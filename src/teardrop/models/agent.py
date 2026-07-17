"""Agent-run and agent metadata models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolPolicy(BaseModel):
    """Per-run tool exclusion policy for agent runs."""

    exclude_names: list[str] = Field(default_factory=list)


class AgentRunRequest(BaseModel):
    message: str = Field(..., max_length=4096)
    thread_id: str = ""
    context: dict[str, Any] | None = None
    emit_ui: bool = True
    tool_policy: ToolPolicy | None = None


class SSEEvent(BaseModel):
    """A single parsed Server-Sent Event from /agent/run."""

    type: str = Field(..., description="Event type, e.g. TEXT_MESSAGE_CONTENT")
    data: dict[str, Any] = Field(default_factory=dict)
    id: str = Field(default="", description="SSE event ID (for stream resumption)")
    retry: int | None = Field(default=None, description="SSE retry interval in ms")


class AgentTool(BaseModel):
    """A tool available for agent runs, as returned by GET /agent/tools."""

    name: str
    source: Literal["platform", "org", "marketplace"]
    access_mode: Literal["included", "subscribed"]


AgentToolItem = AgentTool


class AgentToolsResponse(BaseModel):
    """Envelope response from GET /agent/tools."""

    tools: list[AgentTool] = Field(default_factory=list)


class AgentCard(BaseModel):
    """Minimal representation of the A2A agent card."""

    name: str = ""
    description: str = ""
    url: str = ""
    skills: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class AgentDecisionRecord(BaseModel):
    """Item inside AgentDecisionListResponse."""

    id: str
    run_id: str
    tool_name: str
    decision: str
    created_at: str = ""

    model_config = {"extra": "allow"}


class AgentDecisionListResponse(BaseModel):
    """Response from GET /agent/decisions."""

    items: list[AgentDecisionRecord] = Field(default_factory=list)
    next_cursor: str | None = None


class RunOutcomeResponse(BaseModel):
    """Response from PATCH /agent/runs/{run_id}/outcome."""

    run_id: str
    outcome: str
    updated_at: str = ""

    model_config = {"extra": "allow"}


class EventDispatchResponse(BaseModel):
    """Response from POST /agent/events/{trigger_token}."""

    accepted: bool
    run_id: str | None = None

    model_config = {"extra": "allow"}


class ToolExclusionListResponse(BaseModel):
    """Response from GET /agent/tool-exclusions."""

    exclusions: list[str] = Field(default_factory=list)


class ToolExclusionActionResponse(BaseModel):
    """Response from POST /agent/tool-exclusions."""

    tool_name: str
    excluded: bool

    model_config = {"extra": "allow"}


class ToolExclusionRemovedResponse(BaseModel):
    """Response from DELETE /agent/tool-exclusions/{tool_name}."""

    tool_name: str
    removed: bool

    model_config = {"extra": "allow"}


class TestWebhookResponse(BaseModel):
    """Response from POST /tools/test-webhook."""

    success: bool
    status_code: int | None = None
    response_preview: str = ""

    model_config = {"extra": "allow"}
