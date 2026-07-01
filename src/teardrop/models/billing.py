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
    operation: Literal["debit", "topup"]
    balance_usdc_after: int
    reason: str | None = None
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
