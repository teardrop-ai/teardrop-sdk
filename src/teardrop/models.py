"""Pydantic models for Teardrop SDK requests and responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

# ─── Auth ─────────────────────────────────────────────────────────────────────


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ─── Agent ────────────────────────────────────────────────────────────────────


class AgentRunRequest(BaseModel):
    message: str = Field(..., max_length=4096)
    thread_id: str = ""
    context: dict[str, Any] = Field(default_factory=dict)


class SSEEvent(BaseModel):
    """A single parsed Server-Sent Event from /agent/run."""

    type: str = Field(..., description="Event type, e.g. TEXT_MESSAGE_CONTENT")
    data: dict[str, Any] = Field(default_factory=dict)
    id: str = Field(default="", description="SSE event ID (for stream resumption)")
    retry: int | None = Field(default=None, description="SSE retry interval in ms")


# ─── Billing ──────────────────────────────────────────────────────────────────


class BillingBalance(BaseModel):
    org_id: str
    balance_usdc: int


class PricingInfo(BaseModel):
    billing_enabled: bool = False
    pricing: dict[str, Any] | None = None
    network: str | None = None


class Invoice(BaseModel):
    id: str
    run_id: str
    user_id: str
    org_id: str
    tokens_in: int = 0
    tokens_out: int = 0
    tool_calls: int = 0
    cost_usdc: int = 0
    created_at: datetime | None = None


class CreditHistoryEntry(BaseModel):
    id: str
    org_id: str
    operation: str
    amount_usdc: int
    balance_usdc_after: int
    reason: str = ""
    created_at: datetime | None = None


# ─── Usage ────────────────────────────────────────────────────────────────────


class UsageSummary(BaseModel):
    total_runs: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_tool_calls: int = 0
    total_duration_ms: int = 0


# ─── Wallets ──────────────────────────────────────────────────────────────────


class Wallet(BaseModel):
    id: str
    address: str
    chain_id: int
    user_id: str
    org_id: str
    is_primary: bool = False
    created_at: datetime | None = None


# ─── Agent Card ───────────────────────────────────────────────────────────────


class AgentCard(BaseModel):
    """Minimal representation of the A2A agent card.

    Unknown fields from the API are preserved via ``model_extra``.
    """

    name: str = ""
    description: str = ""
    url: str = ""
    skills: list[dict[str, Any]] = Field(default_factory=list)


# ─── Custom Tools ─────────────────────────────────────────────────────────────


class CreateCustomToolRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str = Field(..., min_length=1, max_length=500)
    input_schema: dict[str, Any] = Field(...)
    webhook_url: str = Field(..., max_length=2048)
    webhook_method: str = Field(default="POST")
    auth_header_name: str | None = Field(default=None, max_length=64)
    auth_header_value: str | None = Field(default=None, max_length=4096)
    timeout_seconds: int = Field(default=10, ge=1, le=30)


class CustomTool(BaseModel):
    id: str
    org_id: str
    name: str
    description: str
    input_schema: dict[str, Any]
    webhook_url: str
    webhook_method: str
    has_auth: bool
    timeout_seconds: int
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"extra": "allow"}


# ─── MCP Servers ──────────────────────────────────────────────────────────────

McpServerAuthType = Literal["none", "bearer", "header"]


class OrgMcpServer(BaseModel):
    """An external MCP server registered for an org.

    The ``name`` field is used as the tool prefix in agent SSE events:
    ``{name}__{mcp_tool_name}``.

    Note: ``auth_token`` is write-only and is **never** returned by the API.
    Only ``has_auth`` (bool) is exposed.
    """

    id: str
    org_id: str
    name: str
    url: str
    auth_type: McpServerAuthType = "none"
    has_auth: bool = False
    auth_header_name: str | None = None
    is_active: bool = True
    timeout_seconds: int = 15
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"extra": "allow"}


class CreateMcpServerRequest(BaseModel):
    """Request body for POST /mcp/servers."""

    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    url: str = Field(..., max_length=2048)
    auth_type: McpServerAuthType = "none"
    auth_token: str | None = None
    auth_header_name: str | None = Field(default=None, max_length=64)
    timeout_seconds: int = Field(default=15, ge=1, le=60)

    @model_validator(mode="after")
    def _check_auth_fields(self) -> "CreateMcpServerRequest":
        if self.auth_type != "none" and not self.auth_token:
            raise ValueError("auth_token is required when auth_type is not 'none'")
        if self.auth_type == "header" and not self.auth_header_name:
            raise ValueError("auth_header_name is required when auth_type is 'header'")
        return self


class UpdateMcpServerRequest(BaseModel):
    """Request body for PATCH /mcp/servers/{server_id}.

    Only explicitly-set fields are sent to the API (``exclude_unset=True``).
    Pass ``auth_token=None`` to explicitly clear a stored token; omitting
    ``auth_token`` entirely leaves the existing token unchanged.
    """

    name: str | None = Field(default=None, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    url: str | None = Field(default=None, max_length=2048)
    auth_type: McpServerAuthType | None = None
    auth_token: str | None = None
    auth_header_name: str | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=60)
    is_active: bool | None = None


class McpToolDefinition(BaseModel):
    """A single tool schema as returned by POST /mcp/servers/{id}/discover."""

    name: str
    description: str
    input_schema: dict[str, Any]


class DiscoverMcpToolsResponse(BaseModel):
    """Response from POST /mcp/servers/{server_id}/discover."""

    server_id: str
    tools: list[McpToolDefinition]
