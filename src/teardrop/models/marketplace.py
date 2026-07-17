"""Marketplace and author-payout models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class MarketplaceTool(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    cost_usdc: int = 0
    author: str = ""
    author_slug: str = ""
    tool_type: str = ""


class MarketplaceCatalogResponse(BaseModel):
    """Response from GET /marketplace/catalog."""

    tools: list[MarketplaceTool]
    next_cursor: str | None = None


class MarketplaceCatalogDetailResponse(BaseModel):
    """Response from GET /marketplace/catalog/{org_slug}/{tool_name}."""

    tool: "MarketplaceToolSummary"


class MarketplaceToolSummary(BaseModel):
    """Summary object used in marketplace import/publish responses."""

    name: str
    qualified_name: str
    tool_name: str
    display_name: str
    description: str
    short_description: str
    input_schema: dict[str, Any]
    cost_usdc: int
    tool_type: str
    category: str
    total_calls: int
    reputation_score: float
    health_status: str
    is_healthy: bool
    author: str
    author_slug: str

    model_config = {"extra": "allow"}


class AuthorConfig(BaseModel):
    org_id: str
    settlement_wallet: str
    created_at: str = ""
    updated_at: str = ""


class MarketplaceAuthorConfigResponse(AuthorConfig):
    """Alias matching the OpenAPI schema name for marketplace author-config."""


class MarketplaceAuthorProfileResponse(BaseModel):
    """Response from GET /marketplace/authors/{org_slug}."""

    org_slug: str
    org_name: str
    tool_count: int
    total_calls: int
    tools: list[MarketplaceToolSummary]
    next_cursor: str | None = None

    model_config = {"extra": "allow"}


class EarningsEntry(BaseModel):
    id: str
    tool_name: str
    total_cost_usdc: int = 0
    caller_org_id: str = ""
    author_share_usdc: int = 0
    platform_share_usdc: int = 0
    status: str = ""
    created_at: str = ""


class MarketplaceEarningEntry(EarningsEntry):
    """Alias matching the OpenAPI schema item name."""

    author_share_usdc: int
    caller_org_id: str
    total_cost_usdc: int
    platform_share_usdc: int
    status: str
    created_at: str


class MarketplaceEarningsResponse(BaseModel):
    """Response from GET /marketplace/earnings."""

    earnings: list[MarketplaceEarningEntry]
    next_cursor: str | None = None


class MarketplaceEarningsByToolEntry(BaseModel):
    """Per-tool earnings aggregate."""

    tool_name: str
    total_calls: int
    total_amount_usdc: int
    total_author_share_usdc: int
    pending_author_share_usdc: int
    settled_author_share_usdc: int
    total_platform_share_usdc: int
    total_cost_usdc: int = 0
    author_share_usdc: int = 0
    platform_share_usdc: int = 0
    runs: int = 0

    model_config = {"extra": "allow"}


class MarketplaceEarningsByToolResponse(BaseModel):
    """Response from GET /marketplace/earnings/by-tool."""

    tools: list[MarketplaceEarningsByToolEntry]
    next_cursor: str | None = None


class MarketplaceBalanceResponse(BaseModel):
    """Response from GET /marketplace/balance."""

    org_id: str
    balance_usdc: int
    pending_usdc: int = 0
    lifetime_earnings_usdc: int = 0

    model_config = {"extra": "allow"}


class WithdrawRequest(BaseModel):
    amount_usdc: int


class MarketplaceWithdrawalResponse(BaseModel):
    """Response from POST /marketplace/withdraw."""

    id: str
    org_id: str
    amount_usdc: int
    wallet: str
    tx_hash: str | None = None
    status: str
    created_at: str

    model_config = {"extra": "allow"}


class MarketplaceWithdrawalHistoryItem(BaseModel):
    """Item inside marketplace withdrawals list."""

    id: str
    amount_usdc: int
    wallet: str
    status: str
    tx_hash: str | None = None
    created_at: str

    model_config = {"extra": "allow"}


class MarketplaceWithdrawalsListResponse(BaseModel):
    """Response from GET /marketplace/withdrawals."""

    withdrawals: list[MarketplaceWithdrawalHistoryItem]
    next_cursor: str | None = None


class CompleteWithdrawalResponse(BaseModel):
    """Response from POST /admin/marketplace/complete-withdrawal/{withdrawal_id}."""

    status: str
    tx_hash: str
    id: str | None = None
    completed_at: str = ""

    model_config = {"extra": "allow"}


class AdminWithdrawalActionResponse(BaseModel):
    """Response from admin marketplace withdrawal process/reset actions."""

    id: str
    org_id: str
    amount_usdc: int
    status: str
    updated_at: str = ""

    model_config = {"extra": "allow"}


class WithdrawalResetResponse(BaseModel):
    """Response from POST /admin/marketplace/reset-withdrawal/{withdrawal_id}."""

    id: str
    status: str
    reset_at: str = ""

    model_config = {"extra": "allow"}


class MarketplaceSweepResponse(BaseModel):
    """Response from POST /admin/marketplace/sweep."""

    processed: int
    tx_hash: str | None = None
    amount_usdc: int | None = None
    swept_at: str = ""

    model_config = {"extra": "allow"}


class SweepStatusItem(BaseModel):
    """Item inside sweep-status response."""

    id: str
    org_id: str
    amount_usdc: int
    status: str
    sweep_attempt_count: int
    created_at: str
    last_sweep_error: str | None = None
    next_sweep_at: str | None = None


class SweepStatusResponse(BaseModel):
    """Response from GET /admin/marketplace/sweep-status."""

    pending: list[SweepStatusItem]
    exhausted: list[SweepStatusItem]


class AdminWithdrawalItem(BaseModel):
    """Item inside AdminWithdrawalListResponse."""

    id: str
    org_id: str
    amount_usdc: int
    wallet: str
    status: str
    created_at: str
    settled_at: str | None = None


class AdminWithdrawalListResponse(BaseModel):
    """Response from GET /admin/marketplace/withdrawals."""

    withdrawals: list[AdminWithdrawalItem]


class MarketplaceSubscription(BaseModel):
    id: str
    org_id: str
    qualified_tool_name: str
    is_active: bool
    subscribed_at: str


MarketplaceSubscriptionItem = MarketplaceSubscription


class MarketplaceSubscriptionResponse(MarketplaceSubscription):
    """Response from POST /marketplace/subscriptions."""


class MarketplaceSubscriptionListResponse(BaseModel):
    """Response from GET /marketplace/subscriptions."""

    subscriptions: list[MarketplaceSubscription]
    next_cursor: str | None = None


class UnsubscribeResponse(BaseModel):
    """Response from DELETE /marketplace/subscriptions/{subscription_id}."""

    unsubscribed: Literal[True]


class RunFeedbackRequest(BaseModel):
    """Request body for marketplace tool feedback."""

    run_id: str = Field(..., min_length=1, max_length=128)
    rating: int = Field(..., ge=-1, le=1)
    comment: str = Field(default="", max_length=1000)


class RunFeedbackResponse(BaseModel):
    """Response from POST /marketplace/tools/{org_slug}/{tool_name}/feedback."""

    id: str
    run_id: str
    qualified_tool_name: str
    rating: int = Field(..., ge=-1, le=1)
    created_at: str


class MarketplaceImportPreviewRequest(BaseModel):
    """Request body for marketplace import preview."""

    server_id: str = Field(..., min_length=1, max_length=128)
    tool_names: list[str] | None = None


class MarketplaceImportPublishToolRequest(BaseModel):
    """Tool request inside marketplace import publish."""

    remote_tool_name: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(..., min_length=1, max_length=500)
    marketplace_description: str | None = Field(default=None, max_length=1000)
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    base_price_usdc: int = Field(default=0, ge=0, le=100_000_000)
    category: str = Field(default="", pattern=r"^(|defi|search|data|communication|utility)$")


class MarketplaceImportPublishRequest(BaseModel):
    """Request body for marketplace import publish."""

    server_id: str = Field(..., min_length=1, max_length=128)
    tools: list[MarketplaceImportPublishToolRequest] = Field(..., min_length=1, max_length=50)


class MarketplaceImportPreviewTool(BaseModel):
    """Tool inside marketplace import preview."""

    remote_tool_name: str
    proposed_name: str
    description: str
    marketplace_description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    schema_status: "ImportPreviewSchemaStatus"
    dropped_schema_features: "ImportPreviewDroppedFeatures"
    name_adjusted: bool
    name_collision_resolved: bool
    quota_exceeded: bool
    publishable: bool
    suggested_base_price_usdc: int
    category: str = ""
    warnings: list[str] = Field(default_factory=list)


class MarketplaceImportPreviewError(BaseModel):
    """Error inside marketplace import preview."""

    remote_tool_name: str
    status_code: int
    error: str


class ImportPreviewSchemaStatus(BaseModel):
    """Schema status inside ImportPreviewDroppedFeatures."""

    input: str
    output: str


class ImportPreviewDroppedFeatures(BaseModel):
    """Dropped features inside marketplace import preview."""

    input: list[str] = Field(default_factory=list)
    output: list[str] = Field(default_factory=list)


class MarketplaceImportPreviewResponse(BaseModel):
    """Response from POST /marketplace/import/preview."""

    server_id: str
    slots_remaining: int
    can_publish: bool
    tools: list[MarketplaceImportPreviewTool]
    errors: list[MarketplaceImportPreviewError]


class MarketplaceImportPublishedTool(BaseModel):
    """Published tool inside marketplace import publish."""

    id: str
    name: str
    org_id: str
    publish_as_mcp: bool
    base_price_usdc: int
    mcp_server_id: str | None = None
    mcp_tool_name: str | None = None

    model_config = {"extra": "allow"}


class MarketplaceImportPublishCreatedItem(BaseModel):
    """Created item inside marketplace import publish response."""

    remote_tool_name: str
    tool: MarketplaceImportPublishedTool


class MarketplaceImportPublishError(BaseModel):
    """Error inside marketplace import publish."""

    remote_tool_name: str
    name: str
    status_code: int
    error: str


class MarketplaceImportPublishResponse(BaseModel):
    """Response from POST /marketplace/import/publish."""

    server_id: str
    created: list[MarketplaceImportPublishCreatedItem]
    errors: list[MarketplaceImportPublishError]

    model_config = {"extra": "allow"}
