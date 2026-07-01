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


class AuthorConfig(BaseModel):
    org_id: str
    settlement_wallet: str
    created_at: str = ""
    updated_at: str = ""


class EarningsEntry(BaseModel):
    id: str
    tool_name: str
    total_cost_usdc: int = 0
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
