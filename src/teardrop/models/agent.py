"""Agent-run and agent metadata models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolPolicy(BaseModel):
    """Per-run tool exclusion policy for agent runs."""

    exclude_names: list[str] = Field(default_factory=list)


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


class ToolExclusionsResponse(BaseModel):
    """Response from GET /agent/tool-exclusions."""

    tool_names: list[str] = Field(default_factory=list)


class ToolExclusionCreateResponse(BaseModel):
    """Response from POST /agent/tool-exclusions."""

    status: str = "added"
    tool_name: str


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

    items: list[DecisionRecord] = Field(default_factory=list)
    next_cursor: str | None = None
