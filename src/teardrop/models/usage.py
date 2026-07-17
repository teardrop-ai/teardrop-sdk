"""Usage summary models."""

from __future__ import annotations

from pydantic import BaseModel


class UsageSummary(BaseModel):
    total_runs: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_tool_calls: int = 0
    total_duration_ms: int = 0

    model_config = {"extra": "allow"}


class PricingRuleWithOverrides(BaseModel):
    """Pricing rule nested in BillingPricingResponse.pricing."""

    id: str
    name: str
    run_price_usdc: int
    tokens_in_cost_per_1k: int = 0
    tokens_out_cost_per_1k: int = 0
    tool_call_cost: int = 0
    tool_overrides: dict[str, int] = {}
    effective_from: str = ""
    created_at: str = ""

    model_config = {"extra": "allow"}
