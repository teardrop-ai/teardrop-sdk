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
    """Pricing rule returned inside some admin/tool pricing responses."""

    tool_name: str
    base_price_usdc: int
    overrides: dict[str, int] = {}
    updated_at: str = ""

    model_config = {"extra": "allow"}
