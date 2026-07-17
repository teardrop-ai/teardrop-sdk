"""Billing and payment models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolPricing(BaseModel):
    tool_name: str
    price_usdc: int
    description: str


class BillingPricingResponse(BaseModel):
    tools: list[ToolPricing] = Field(default_factory=list)
    base_cost_usdc: int = 0
    updated_at: str = ""


PricingInfo = BillingPricingResponse


class CreditBalance(BaseModel):
    org_id: str
    balance_usdc: int
    spending_limit_usdc: int = 0
    is_paused: bool = False
    daily_spend_usdc: int = 0


BillingBalance = CreditBalance


class BillingBalanceResponse(CreditBalance):
    """Alias matching the OpenAPI schema name for GET /billing/balance."""


class BillingHistoryEntry(BaseModel):
    run_id: str
    user_id: str
    amount_usdc: int
    method: Literal["credit", "x402"]
    status: Literal["pending", "settled", "failed"]
    created_at: str


class BillingHistoryItem(BillingHistoryEntry):
    """Alias matching the OpenAPI schema name for GET /billing/history."""


class Invoice(BaseModel):
    run_id: str
    tokens_in: int = 0
    tokens_out: int = 0
    tool_calls: int = 0
    total_usdc: int = 0
    breakdown: list[dict[str, Any]] = Field(default_factory=list)
    settled_at: str = ""


class InvoiceItem(Invoice):
    """Alias matching the OpenAPI schema name for GET /billing/invoice/{run_id}."""


class InvoiceListResponse(BaseModel):
    """Response from GET /billing/invoices."""

    items: list[Invoice] = Field(default_factory=list)
    next_cursor: str | None = None


class CreditHistoryEntry(BaseModel):
    id: str
    amount_usdc: int
    operation: Literal["debit", "topup"]
    balance_usdc_after: int
    reason: str | None = None
    created_at: str


class CreditHistoryResponse(BaseModel):
    """Response from GET /billing/credit-history."""

    items: list[CreditHistoryEntry] = Field(default_factory=list)
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


class UsdcTopupRequest(BaseModel):
    amount_usdc: int
    payment_header: str


class UsdcTopupResponse(BaseModel):
    """Response from POST /billing/topup/usdc."""

    credited_usdc: int
    new_balance_usdc: int | None = None

    model_config = {"extra": "allow"}


class AdminTopupResponse(BaseModel):
    """Response from POST /admin/credits/topup."""

    org_id: str
    amount_usdc: int
    new_balance_usdc: int
    created_at: str = ""

    model_config = {"extra": "allow"}


class PendingSettlementsResponse(BaseModel):
    """Response from GET /admin/billing/pending."""

    items: list[dict[str, Any]] = Field(default_factory=list)
    next_cursor: str | None = None


class PendingSettlementItem(BaseModel):
    """Item inside PendingSettlementsResponse."""

    id: str
    org_id: str
    amount_usdc: int
    status: str
    created_at: str = ""

    model_config = {"extra": "allow"}


class SettlementRetryResponse(BaseModel):
    """Response from POST /admin/billing/pending/{settlement_id}/retry."""

    id: str
    status: str
    retried_at: str = ""

    model_config = {"extra": "allow"}


class RevenueSummaryResponse(BaseModel):
    """Response from GET /admin/billing/revenue."""

    total_revenue_usdc: int
    period_start: str = ""
    period_end: str = ""

    model_config = {"extra": "allow"}


class SettlementBalanceResponse(BaseModel):
    """Response from GET /admin/marketplace/settlement-balance."""

    balance_usdc: int
    updated_at: str = ""

    model_config = {"extra": "allow"}


class ToolPricingOverrideResponse(BaseModel):
    """Response from POST /admin/pricing/tools."""

    tool_name: str
    price_usdc: int
    updated_at: str = ""

    model_config = {"extra": "allow"}


class ToolPricingDeleteResponse(BaseModel):
    """Response from DELETE /admin/pricing/tools/{tool_name}."""

    tool_name: str
    deleted_at: str = ""

    model_config = {"extra": "allow"}
