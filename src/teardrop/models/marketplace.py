"""Marketplace and author-payout models."""

from __future__ import annotations

from typing import Any

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

    tools: list[MarketplaceTool] = Field(default_factory=list)
    next_cursor: str | None = None


class MarketplaceCatalogDetailResponse(MarketplaceTool):
    """Response from GET /marketplace/catalog/{org_slug}/{tool_name}."""

    org_id: str = ""
    created_at: str = ""
    updated_at: str = ""


class MarketplaceToolSummary(BaseModel):
    """Summary object used in marketplace import/publish responses."""

    name: str
    qualified_name: str
    cost_usdc: int = 0

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

    org_id: str
    org_slug: str
    display_name: str = ""
    bio: str = ""
    website: str = ""
    created_at: str = ""

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


class MarketplaceEarningsResponse(BaseModel):
    """Response from GET /marketplace/earnings."""

    earnings: list[EarningsEntry] = Field(default_factory=list)
    next_cursor: str | None = None


class MarketplaceEarningsByToolEntry(BaseModel):
    """Per-tool earnings aggregate."""

    tool_name: str
    total_cost_usdc: int = 0
    author_share_usdc: int = 0
    platform_share_usdc: int = 0
    runs: int = 0

    model_config = {"extra": "allow"}


class MarketplaceEarningsByToolResponse(BaseModel):
    """Response from GET /marketplace/earnings/by-tool."""

    tools: list[MarketplaceEarningsByToolEntry] = Field(default_factory=list)
    next_cursor: str | None = None


class MarketplaceBalanceResponse(BaseModel):
    """Response from GET /marketplace/balance."""

    balance_usdc: int
    pending_usdc: int = 0
    lifetime_earnings_usdc: int = 0

    model_config = {"extra": "allow"}


class WithdrawRequest(BaseModel):
    amount_usdc: int


class MarketplaceWithdrawalResponse(BaseModel):
    """Response from POST /marketplace/withdraw."""

    id: str
    amount_usdc: int
    tx_hash: str | None = None
    status: str = ""
    created_at: str = ""

    model_config = {"extra": "allow"}


class MarketplaceWithdrawalHistoryItem(BaseModel):
    """Item inside marketplace withdrawals list."""

    id: str
    amount_usdc: int
    status: str
    tx_hash: str | None = None
    created_at: str = ""

    model_config = {"extra": "allow"}


class MarketplaceWithdrawalsListResponse(BaseModel):
    """Response from GET /marketplace/withdrawals."""

    withdrawals: list[MarketplaceWithdrawalHistoryItem] = Field(default_factory=list)
    next_cursor: str | None = None


class CompleteWithdrawalResponse(BaseModel):
    """Response from POST /admin/marketplace/complete-withdrawal/{withdrawal_id}."""

    id: str
    tx_hash: str
    completed_at: str = ""

    model_config = {"extra": "allow"}


class AdminWithdrawalActionResponse(BaseModel):
    """Response from admin marketplace withdrawal process/reset actions."""

    id: str
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

    tx_hash: str | None = None
    amount_usdc: int = 0
    swept_at: str = ""

    model_config = {"extra": "allow"}


class SweepStatusItem(BaseModel):
    """Item inside sweep-status response."""

    tx_hash: str | None = None
    amount_usdc: int = 0
    status: str
    created_at: str = ""

    model_config = {"extra": "allow"}


class SweepStatusResponse(BaseModel):
    """Response from GET /admin/marketplace/sweep-status."""

    items: list[SweepStatusItem] = Field(default_factory=list)
    next_cursor: str | None = None


class MarketplaceSubscription(BaseModel):
    id: str
    org_id: str
    qualified_tool_name: str
    is_active: bool = True
    subscribed_at: str = ""


MarketplaceSubscriptionItem = MarketplaceSubscription


class MarketplaceSubscriptionResponse(MarketplaceSubscription):
    """Response from POST /marketplace/subscriptions."""


class MarketplaceSubscriptionListResponse(BaseModel):
    """Response from GET /marketplace/subscriptions."""

    subscriptions: list[MarketplaceSubscription] = Field(default_factory=list)
    next_cursor: str | None = None


class UnsubscribeResponse(BaseModel):
    """Response from DELETE /marketplace/subscriptions/{subscription_id}."""

    subscription_id: str
    unsubscribed_at: str = ""

    model_config = {"extra": "allow"}


class RunFeedbackResponse(BaseModel):
    """Response from POST /marketplace/tools/{org_slug}/{tool_name}/feedback."""

    id: str
    message: str = ""
    created_at: str = ""

    model_config = {"extra": "allow"}


class MarketplaceImportPreviewTool(BaseModel):
    """Tool inside marketplace import preview."""

    name: str
    qualified_name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    cost_usdc: int = 0
    issues: list[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class MarketplaceImportPreviewError(BaseModel):
    """Error inside marketplace import preview."""

    tool_name: str
    reason: str

    model_config = {"extra": "allow"}


class ImportPreviewSchemaStatus(BaseModel):
    """Schema status inside ImportPreviewDroppedFeatures."""

    compatible: bool = False
    notes: str = ""

    model_config = {"extra": "allow"}


class ImportPreviewDroppedFeatures(BaseModel):
    """Dropped features inside marketplace import preview."""

    authentication: bool = False
    schema: ImportPreviewSchemaStatus = Field(default_factory=ImportPreviewSchemaStatus)

    model_config = {"extra": "allow"}


class MarketplaceImportPreviewResponse(BaseModel):
    """Response from POST /marketplace/import/preview."""

    tools: list[MarketplaceImportPreviewTool] = Field(default_factory=list)
    errors: list[MarketplaceImportPreviewError] = Field(default_factory=list)
    dropped_features: ImportPreviewDroppedFeatures = Field(
        default_factory=ImportPreviewDroppedFeatures
    )

    model_config = {"extra": "allow"}


class MarketplaceImportPublishToolRequest(BaseModel):
    """Tool request inside marketplace import publish."""

    name: str
    qualified_name: str | None = None
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    cost_usdc: int = 0

    model_config = {"extra": "allow"}


class MarketplaceImportPublishedTool(BaseModel):
    """Published tool inside marketplace import publish."""

    name: str
    qualified_name: str
    published_at: str = ""

    model_config = {"extra": "allow"}


class MarketplaceImportPublishCreatedItem(BaseModel):
    """Created item inside marketplace import publish response."""

    tool: MarketplaceImportPublishedTool = Field(default_factory=dict)
    cost_usdc: int = 0

    model_config = {"extra": "allow"}


class MarketplaceImportPublishError(BaseModel):
    """Error inside marketplace import publish."""

    tool_name: str
    reason: str

    model_config = {"extra": "allow"}


class MarketplaceImportPublishResponse(BaseModel):
    """Response from POST /marketplace/import/publish."""

    created: list[MarketplaceImportPublishCreatedItem] = Field(default_factory=list)
    errors: list[MarketplaceImportPublishError] = Field(default_factory=list)

    model_config = {"extra": "allow"}
