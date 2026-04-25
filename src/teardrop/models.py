"""Pydantic models for Teardrop SDK requests and responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

# ─── Auth ─────────────────────────────────────────────────────────────────────


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str | None = None


class JwtPayloadBase(BaseModel):
    """Decoded JWT payload returned by GET /auth/me."""

    sub: str | None = None
    user_id: str | None = None
    org_id: str = ""
    role: str = ""
    auth_method: str = ""
    email: str | None = None
    iss: str | None = None
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


class MeResponse(JwtPayloadBase):
    """Response from GET /auth/me — JWT claims plus org_name resolved from the database."""

    org_name: str = ""
    """Org display name; empty string for config-based client_credentials tokens with no org row."""


# ─── Agent ────────────────────────────────────────────────────────────────────


class AgentRunRequest(BaseModel):
    message: str = Field(..., max_length=4096)
    thread_id: str = ""
    context: dict[str, Any] | None = None


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


class CreditBalance(BaseModel):
    org_id: str
    balance_usdc: int
    spending_limit_usdc: int = 0
    is_paused: bool = False
    daily_spend_usdc: int = 0


# Backward-compat alias
BillingBalance = CreditBalance


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
    amount_cents: int
    return_url: str


class StripeTopupResponse(BaseModel):
    client_secret: str
    session_id: str


class StripeTopupStatusResponse(BaseModel):
    status: Literal["open", "complete", "expired"]
    new_balance_fmt: str | None = None


class UsdcTopupRequirements(BaseModel):
    accepts: list[dict[str, Any]] = Field(default_factory=list)
    x402Version: int = 2


class UsdcTopupRequest(BaseModel):
    amount_usdc: int
    payment_header: str


# ─── Usage ────────────────────────────────────────────────────────────────────


class UsageSummary(BaseModel):
    total_runs: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_tool_calls: int = 0
    total_duration_ms: int = 0


# ─── Wallets ──────────────────────────────────────────────────────────────────


class LinkWalletRequest(BaseModel):
    siwe_message: str
    siwe_signature: str


class Wallet(BaseModel):
    id: str
    org_id: str = ""
    user_id: str | None = None
    address: str
    chain_id: int
    is_primary: bool = False
    created_at: str = ""

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
    webhook_method: str | None = None
    auth_header_name: str | None = None
    auth_header_value: str | None = None
    timeout_seconds: int | None = None  # default 10, max 30
    publish_as_mcp: bool | None = None
    marketplace_description: str | None = None
    base_price_usdc: int | None = None


# Backward-compat alias
CreateCustomToolRequest = CreateOrgToolRequest


class UpdateOrgToolRequest(BaseModel):
    description: str | None = None
    input_schema: dict[str, Any] | None = None
    webhook_url: str | None = None
    webhook_method: str | None = None
    auth_header_name: str | None = None
    auth_header_value: str | None = None
    timeout_seconds: int | None = None
    is_active: bool | None = None
    publish_as_mcp: bool | None = None
    marketplace_description: str | None = None
    base_price_usdc: int | None = None


class OrgTool(BaseModel):
    id: str
    org_id: str
    name: str
    description: str
    input_schema: dict[str, Any]
    webhook_url: str
    webhook_method: str = "POST"
    has_auth: bool = False
    is_active: bool = True
    publish_as_mcp: bool = False
    marketplace_description: str | None = None
    base_price_usdc: int | None = None
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
    content: str = Field(..., min_length=1, max_length=500)


class MemoryEntry(BaseModel):
    id: str
    content: str
    created_at: str = ""


# ─── Marketplace ──────────────────────────────────────────────────────────────


class MarketplaceTool(BaseModel):
    name: str  # qualified name: "{org_slug}/{tool_name}" or "platform/{tool_name}"
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    cost_usdc: int = 0
    author: str = ""  # author org display name (e.g. "Teardrop" for platform tools)
    author_slug: str = ""  # author org slug (e.g. "platform" for Teardrop built-in tools)


class AuthorConfig(BaseModel):
    org_id: str
    settlement_wallet: str
    created_at: str = ""
    updated_at: str = ""


class EarningsEntry(BaseModel):
    id: str
    tool_name: str
    total_cost_usdc: int = 0  # total charged to the caller
    caller_org_id: str = ""
    author_share_usdc: int = 0
    platform_share_usdc: int = 0
    status: str = ""
    created_at: str = ""


class WithdrawRequest(BaseModel):
    amount_usdc: int


class MarketplaceSubscription(BaseModel):
    id: str
    org_id: str
    qualified_tool_name: str
    is_active: bool = True
    subscribed_at: str = ""


# ─── LLM Config ───────────────────────────────────────────────────────────────

ProviderType = Literal["anthropic", "openai", "google", "openrouter"]
RoutingPreference = Literal["default", "cost", "speed", "quality"]

MODELS_BY_PROVIDER: dict[str, list[str]] = {
    "anthropic": ["claude-haiku-4-5-20251001", "claude-sonnet-4-20250514"],
    "openai": ["gpt-4o-mini", "gpt-4o"],
    "google": ["gemini-2.0-flash", "gemini-2.5-pro"],
    "openrouter": [],
}


class OrgLlmConfig(BaseModel):
    """Org LLM configuration as returned by GET /llm-config and PUT /llm-config."""

    org_id: str = ""
    provider: str = ""
    model: str = ""
    has_api_key: bool = False
    api_base: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.0
    timeout_seconds: int = 120
    routing_preference: str = "default"
    is_byok: bool = False
    created_at: str = ""
    updated_at: str = ""

    model_config = {"extra": "allow"}


class SetLlmConfigRequest(BaseModel):
    """Request body for PUT /llm-config."""

    provider: ProviderType
    model: str
    api_key: str | None = None
    api_base: str | None = None
    max_tokens: int = Field(default=4096, ge=1, le=200_000)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    timeout_seconds: int = Field(default=120, ge=1)
    routing_preference: RoutingPreference = "default"


# ─── Model Benchmarks ─────────────────────────────────────────────────────────


class ModelPricing(BaseModel):
    tokens_in_cost_per_1k: float = 0.0
    tokens_out_cost_per_1k: float = 0.0
    tool_call_cost: float = 0.0


class ModelRunBenchmarks(BaseModel):
    total_runs_7d: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    avg_cost_usdc_per_run: float = 0.0
    avg_tokens_per_sec: float = 0.0


class ModelInfo(BaseModel):
    """A single model entry in the benchmarks catalogue."""

    provider: str = ""
    model: str = ""
    display_name: str = ""
    context_window: int = 0
    supports_tools: bool = False
    supports_streaming: bool = False
    quality_tier: int = 0
    knowledge_cutoff: str = ""  # model training data cutoff date (e.g. "2025-10") or "Unknown"
    training_cutoff_note: str = ""  # human-readable description (e.g. "Training data through October 2025")
    pricing: ModelPricing = Field(default_factory=ModelPricing)
    benchmarks: ModelRunBenchmarks | None = None

    model_config = {"extra": "allow"}


class ModelBenchmarksResponse(BaseModel):
    """Response for GET /models/benchmarks and GET /models/benchmarks/org."""

    models: list[ModelInfo] = Field(default_factory=list)
    updated_at: str = ""


# ─── A2A Delegation ───────────────────────────────────────────────────────────


class AddTrustedAgentRequest(BaseModel):
    agent_url: str
    label: str | None = None
    max_cost_usdc: int | None = None
    require_x402: bool = False
    jwt_forward: bool = False


class TrustedAgent(BaseModel):
    id: str
    org_id: str | None = None  # present on create response; absent from list response
    agent_url: str
    label: str | None = None
    max_cost_usdc: int = 0
    require_x402: bool = False
    jwt_forward: bool = False
    created_at: str | None = None  # present on list response; absent from create response

    model_config = {"extra": "allow"}


# ─── Org Credentials ─────────────────────────────────────────────────────────


class OrgCredentialsEntry(BaseModel):
    """A single M2M credential entry (secret is never returned)."""

    client_id: str
    created_at: str = ""


class OrgCredentialsResponse(BaseModel):
    """Response from GET /org/credentials."""

    credentials: list[OrgCredentialsEntry] = Field(default_factory=list)


class RegenerateCredentialsResponse(BaseModel):
    """Response from POST /org/credentials/regenerate.

    ``client_secret`` is returned exactly once — callers must store it immediately.
    """

    client_id: str
    client_secret: str  # plaintext; never retrievable after this response
    created_at: str = ""


# ─── Agent Wallets ─────────────────────────────────────────────────────────────


class AgentWallet(BaseModel):
    """CDP-backed agent wallet provisioned per-org."""

    id: str = ""
    org_id: str = ""
    address: str = ""
    network: str = ""
    is_active: bool = True
    created_at: str = ""

    model_config = {"extra": "allow"}
