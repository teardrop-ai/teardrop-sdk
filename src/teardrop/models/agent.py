"""Agent-run and agent metadata models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolPolicy(BaseModel):
    """Per-run tool exclusion policy for agent runs."""

    exclude_names: list[str] = Field(default_factory=list, max_length=50)


class ToolExclusionRequest(BaseModel):
    """Request body for POST /agent/tool-exclusions."""

    tool_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Internal tool name to exclude (unprefixed, e.g. 'web_search').",
    )


class RunOutcomeRequest(BaseModel):
    """Request body for PATCH /agent/runs/{run_id}/outcome."""

    rating: int = Field(..., ge=-1, le=1, description="-1 (bad), 0 (neutral), or 1 (good).")


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
    qualified_name: str
    display_name: str
    description: str
    cost_usdc: int
    input_schema: dict[str, Any]


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
    outcome: int = Field(..., ge=-1, le=1)
    created_at: str
    action: str = ""
    confidence: float | None = None
    outcome_source: str = ""
    reasoning: str = ""
    task_class: str = ""
    tool_names: list[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class AgentDecisionListResponse(BaseModel):
    """Response from GET /agent/decisions."""

    items: list[AgentDecisionRecord]
    next_cursor: str | None = None


class RunOutcomeResponse(BaseModel):
    """Response from PATCH /agent/runs/{run_id}/outcome."""

    status: Literal["recorded"]


class DecisionRecord(BaseModel):
    """A single decision graph record representing a completed agent run action."""

    id: str
    run_id: str
    task_class: str | None = None
    action: str
    reasoning: str
    confidence: float
    tool_names: list[str] = Field(default_factory=list)
    outcome: int | None = None
    outcome_source: str | None = None
    created_at: str


class AgentDecisionsResponse(BaseModel):
    """Paginated list of decision-graph records."""

    items: list[AgentDecisionRecord] = Field(default_factory=list)
    next_cursor: str | None = None


class EventDispatchResponse(BaseModel):
    """Response from POST /agent/events/{trigger_token}."""

    accepted: bool
    run_id: str | None
    status: str
    schedule_id: str | None
    result_path: str | None

    model_config = {"extra": "allow"}


class ToolExclusionListResponse(BaseModel):
    """Response from GET /agent/tool-exclusions."""

    tool_names: list[str]


class ToolExclusionsResponse(ToolExclusionListResponse):
    """Response from GET /agent/tool-exclusions."""


class ToolExclusionActionResponse(BaseModel):
    """Response from POST /agent/tool-exclusions."""

    status: Literal["added"]
    tool_name: str


class ToolExclusionCreateResponse(BaseModel):
    """Response from POST /agent/tool-exclusions."""

    status: Literal["added"]
    tool_name: str


class ToolExclusionRemovedResponse(BaseModel):
    """Response from DELETE /agent/tool-exclusions/{tool_name}."""

    status: Literal["removed"]
    tool_name: str


class TestWebhookResponse(BaseModel):
    """Response from POST /tools/test-webhook."""

    success: bool
    status_code: int | None = None
    response_preview: str = ""

    model_config = {"extra": "allow"}
