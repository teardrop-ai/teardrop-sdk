"""Pydantic models for Teardrop SDK requests and responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

# ─── Auth ─────────────────────────────────────────────────────────────────────


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class JwtPayloadBase(BaseModel):
    """Decoded JWT payload returned by GET /auth/me."""

    sub: str | None = None
    user_id: str | None = None
    org_id: str = ""
    role: str = ""
    auth_method: str = ""
    email: str | None = None
    exp: int | None = None
    iat: int | None = None
    # SIWE-specific fields (present when auth_method == "siwe")
    address: str | None = None
    chain_id: int | None = None

    @property
    def effective_sub(self) -> str | None:
        """Return sub or user_id — whichever is present."""
        return self.sub or self.user_id

    model_config = {"extra": "allow"}


# ─── Agent ────────────────────────────────────────────────────────────────────


class AgentRunRequest(BaseModel):
    prompt: str = Field(..., max_length=4096, serialization_alias="message")
    thread_id: str = ""
    model: str | None = None
    x402_payment_header: str | None = None
    payment_signature: str | None = None


class SSEEvent(BaseModel):
    """A single parsed Server-Sent Event from /agent/run."""

    type: str = Field(..., description="Event type, e.g. TEXT_MESSAGE_CONTENT")
    data: dict[str, Any] = Field(default_factory=dict)
    id: str = Field(default="", description="SSE event ID (for stream resumption)")
    retry: int | None = Field(default=None, description="SSE retry interval in ms")


# ─── Billing ──────────────────────────────────────────────────────────────────


class ToolPricing(BaseModel):
    tool_name: str
    price_usdc: int
    description: str


class BillingPricingResponse(BaseModel):
    tools: list[ToolPricing] = Field(default_factory=list)
    base_cost_usdc: int = 0
    updated_at: str = ""


# Backward-compat alias
PricingInfo = BillingPricingResponse


class BillingBalance(BaseModel):
    org_id: str
    balance_usdc: int
    reserved_usdc: int = 0
    available_usdc: int = 0
    updated_at: str = ""


# Spec alias
CreditBalance = BillingBalance


class BillingHistoryEntry(BaseModel):
    run_id: str
    user_id: str
    amount_usdc: int
    method: Literal["credit", "x402"]
    status: Literal["pending", "settled", "failed"]
    created_at: str


class Invoice(BaseModel):
    run_id: str
    tokens_in: int = 0
    tokens_out: int = 0
    tool_calls: int = 0
    total_usdc: int = 0
    breakdown: list[dict[str, Any]] = Field(default_factory=list)
    settled_at: str = ""


class CreditHistoryEntry(BaseModel):
    id: str
    amount_usdc: int
    method: Literal["stripe", "usdc", "admin"]
    reference: str | None = None
    created_at: str


class StripeTopupRequest(BaseModel):
    amount_usdc: int
    success_url: str
    cancel_url: str


class StripeTopupResponse(BaseModel):
    session_id: str
    checkout_url: str


class StripeTopupStatusResponse(BaseModel):
    session_id: str
    status: Literal["open", "complete", "expired"]
    amount_usdc: int | None = None


class UsdcTopupRequirements(BaseModel):
    payto_address: str
    token_address: str
    network: str
    chain_id: int
    min_amount_usdc: int
    authorization_type: str = "EIP-3009"


class UsdcTopupRequest(BaseModel):
    amount_usdc: int
    authorization: str
    signature: str
    tx_hash: str | None = None


# ─── Usage ────────────────────────────────────────────────────────────────────


class UsageSummary(BaseModel):
    user_id: str = ""
    org_id: str = ""
    period_from: str = ""
    period_to: str = ""
    total_runs: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_tool_calls: int = 0
    total_cost_usdc: int = 0


# ─── Wallets ──────────────────────────────────────────────────────────────────


class LinkWalletRequest(BaseModel):
    message: str
    signature: str
    nonce: str


class Wallet(BaseModel):
    id: str
    user_id: str | None = None
    address: str
    chain_id: int
    is_primary: bool = False
    linked_at: str = ""

    model_config = {"extra": "allow"}


# ─── Agent Card ───────────────────────────────────────────────────────────────


class AgentCard(BaseModel):
    """Minimal representation of the A2A agent card.

    Unknown fields from the API are preserved via ``model_extra``.
    """

    name: str = ""
    description: str = ""
    url: str = ""
    skills: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"extra": "allow"}


# ─── Org Webhook Tools ────────────────────────────────────────────────────────


class CreateOrgToolRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(..., min_length=1, max_length=500)
    input_schema: dict[str, Any] = Field(...)
    webhook_url: str = Field(..., max_length=2048)
    webhook_secret: str | None = None


# Backward-compat alias
CreateCustomToolRequest = CreateOrgToolRequest


class UpdateOrgToolRequest(BaseModel):
    description: str | None = None
    input_schema: dict[str, Any] | None = None
    webhook_url: str | None = None
    webhook_secret: str | None = None
    is_active: bool | None = None


class OrgTool(BaseModel):
    id: str
    org_id: str
    name: str
    description: str
    input_schema: dict[str, Any]
    webhook_url: str
    has_auth: bool
    is_active: bool
    created_at: str = ""
    updated_at: str = ""

    model_config = {"extra": "allow"}


# Backward-compat alias
CustomTool = OrgTool


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
    created_at: str = ""
    updated_at: str = ""

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
    server_name: str = ""
    tools: list[McpToolDefinition]
    discovered_at: str = ""


# ─── Memory ───────────────────────────────────────────────────────────────────


class StoreMemoryRequest(BaseModel):
    content: str
    metadata: dict[str, Any] | None = None
    ttl_seconds: int | None = None


class MemoryEntry(BaseModel):
    id: str
    org_id: str
    content: str
    metadata: dict[str, Any] | None = None
    created_at: str = ""
    expires_at: str | None = None


class MemoryListResponse(BaseModel):
    items: list[MemoryEntry]
    total: int = 0
    next_cursor: str | None = None


# ─── Marketplace ──────────────────────────────────────────────────────────────


class MarketplaceTool(BaseModel):
    id: str
    name: str
    description: str
    author_org_id: str
    price_usdc: int
    tags: list[str] = Field(default_factory=list)
    mcp_server_url: str
    is_active: bool = True
    created_at: str = ""


class AuthorConfig(BaseModel):
    org_id: str
    payout_address: str
    is_verified: bool = False
    created_at: str = ""
    updated_at: str = ""


class EarningsEntry(BaseModel):
    id: str
    tool_name: str
    amount_usdc: int
    buyer_org_id: str
    created_at: str = ""


class WithdrawRequest(BaseModel):
    amount_usdc: int
    payout_address: str | None = None
