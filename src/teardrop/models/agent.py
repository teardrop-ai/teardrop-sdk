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
