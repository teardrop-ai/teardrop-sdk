"""Billing and payment models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from teardrop.models.usage import PricingRuleWithOverrides


class ToolPricing(BaseModel):
    tool_name: str
    price_usdc: int
    description: str


class BillingPricingResponse(BaseModel):
    tools: list[ToolPricing] = Field(default_factory=list)
    base_cost_usdc: int = 0
    updated_at: str = ""
    billing_enabled: bool
    network: str | None = None
    pricing: PricingRuleWithOverrides | None = None


PricingInfo = BillingPricingResponse


class CreditBalance(BaseModel):
    org_id: str
    balance_usdc: int
    spending_limit_usdc: int = 0
    spending_limit_active: bool = False
    is_paused: bool = False
    daily_spend_usdc: int = 0


BillingBalance = CreditBalance


class BillingBalanceResponse(CreditBalance):
    """Alias matching the OpenAPI schema name for GET /billing/balance."""

    spending_limit_usdc: int
    spending_limit_active: bool
    is_paused: bool
    daily_spend_usdc: int


class BillingHistoryEntry(BaseModel):
    id: str = ""
    run_id: str = ""
    user_id: str = ""
    amount_usdc: int = 0
    method: Literal["credit", "x402"] = "credit"
    status: Literal["pending", "settled", "failed"] = "pending"
    tokens_in: int = 0
    tokens_out: int = 0
    tool_calls: int = 0
    tool_names: list[str] = Field(default_factory=list)
    duration_ms: int = 0
    cost_usdc: int = 0
    platform_fee_usdc: int = 0
    settlement_tx: str | None = None
    settlement_status: str = ""
    created_at: str = ""


class BillingHistoryItem(BillingHistoryEntry):
    """Alias matching the OpenAPI schema name for GET /billing/history."""

    id: str
    run_id: str
    tokens_in: int
    tokens_out: int
    tool_calls: int
    tool_names: list[str]
    duration_ms: int
    cost_usdc: int
    platform_fee_usdc: int
    settlement_tx: str | None
    settlement_status: str
    created_at: str


class Invoice(BaseModel):
    id: str = ""
    run_id: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    tool_calls: int = 0
    tool_names: list[str] = Field(default_factory=list)
    duration_ms: int = 0
    cost_usdc: int = 0
    platform_fee_usdc: int = 0
    settlement_tx: str | None = None
    settlement_status: str = ""
    created_at: str = ""
    thread_id: str = ""
    total_usdc: int = 0
    breakdown: list[dict[str, Any]] = Field(default_factory=list)
    settled_at: str = ""


class InvoiceItem(Invoice):
    """Alias matching the OpenAPI schema name for GET /billing/invoice/{run_id}."""

    id: str
    run_id: str
    tokens_in: int
    tokens_out: int
    tool_calls: int
    tool_names: list[str]
    duration_ms: int
    cost_usdc: int
    platform_fee_usdc: int
    settlement_tx: str | None
    settlement_status: str
    created_at: str
    thread_id: str


class InvoiceListResponse(BaseModel):
    """Response from GET /billing/invoices."""

    items: list[InvoiceItem]
    next_cursor: str | None = None


class CreditHistoryEntry(BaseModel):
    id: str
    org_id: str
    amount_usdc: int
    operation: Literal["debit", "topup"]
    balance_usdc_after: int
    reason: str | None
    created_at: str


class CreditHistoryResponse(BaseModel):
    """Response from GET /billing/credit-history."""

    items: list[CreditHistoryEntry]
    next_cursor: str | None = None


class StripeTopupRequest(BaseModel):
    amount_cents: int
    return_url: str


class StripeTopupResponse(BaseModel):
    client_secret: str
    session_id: str


StripeTopupSessionResponse = StripeTopupResponse


class StripeSessionStatusResponse(BaseModel):
    status: Literal["open", "complete", "expired"]
    new_balance_fmt: str | None = None


StripeTopupStatusResponse = StripeSessionStatusResponse


class UsdcTopupRequirements(BaseModel):
    accepts: list[dict[str, Any]] = Field(default_factory=list)
    x402Version: int = 2


class UsdcTopupRequirementsResponse(UsdcTopupRequirements):
    """Alias matching the OpenAPI schema name for GET /billing/topup/usdc/requirements."""

    accepts: list[dict[str, Any]]
    x402Version: int


class UsdcTopupRequest(BaseModel):
    amount_usdc: int
    payment_header: str


class UsdcTopupResponse(BaseModel):
    """Response from POST /billing/topup/usdc."""

    credited_usdc: int = 0
    new_balance_usdc: int | None = None
    status: str
    amount_usdc: int
    balance_usdc: int
    tx_hash: str

    model_config = {"extra": "allow"}


class AdminTopupResponse(BaseModel):
    """Response from POST /admin/credits/topup."""

    org_id: str
    new_balance_usdc: int
    amount_usdc: int | None = None
    created_at: str = ""

    model_config = {"extra": "allow"}


class PendingSettlementItem(BaseModel):
    """Item inside PendingSettlementsResponse."""

    id: str
    usage_event_id: str
    org_id: str
    run_id: str
    billing_method: str
    amount_usdc: int
    retry_count: int
    max_retries: int
    status: str
    created_at: str
    last_error: str | None = None
    next_retry_at: str | None = None

    model_config = {"extra": "allow"}


class PendingSettlementsResponse(BaseModel):
    """Response from GET /admin/billing/pending."""

    items: list[PendingSettlementItem]


class SettlementRetryResponse(BaseModel):
    """Response from POST /admin/billing/pending/{settlement_id}/retry."""

    settlement_id: str
    status: Literal["pending"]
    retried_at: str = ""

    model_config = {"extra": "allow"}


class RevenueSummaryResponse(BaseModel):
    """Response from GET /admin/billing/revenue."""

    total_settlements: int
    total_revenue_usdc: int
    period_start: str = ""
    period_end: str = ""

    model_config = {"extra": "allow"}


class SettlementBalanceResponse(BaseModel):
    """Response from GET /admin/marketplace/settlement-balance."""

    account: str
    address: str
    chain_id: int
    balance_usdc: int
    updated_at: str = ""

    model_config = {"extra": "allow"}


class ToolPricingOverrideResponse(BaseModel):
    """Response from POST /admin/pricing/tools."""

    tool_name: str
    cost_usdc: int
    description: str
    updated: bool


class ToolPricingDeleteResponse(BaseModel):
    """Response from DELETE /admin/pricing/tools/{tool_name}."""

    tool_name: str
    deleted: bool
