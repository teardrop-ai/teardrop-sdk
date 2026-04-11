"""Pydantic models for Teardrop SDK requests and responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ─── Auth ─────────────────────────────────────────────────────────────────────


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ─── Agent ────────────────────────────────────────────────────────────────────


class AgentRunRequest(BaseModel):
    message: str = Field(..., max_length=4096)
    thread_id: str = ""
    context: dict[str, Any] = Field(default_factory=dict)


class SSEEvent(BaseModel):
    """A single parsed Server-Sent Event from /agent/run."""

    type: str = Field(..., description="Event type, e.g. TEXT_MESSAGE_CONTENT")
    data: dict[str, Any] = Field(default_factory=dict)
    id: str = Field(default="", description="SSE event ID (for stream resumption)")
    retry: int | None = Field(default=None, description="SSE retry interval in ms")


# ─── Billing ──────────────────────────────────────────────────────────────────


class BillingBalance(BaseModel):
    org_id: str
    balance_usdc: int


class PricingInfo(BaseModel):
    billing_enabled: bool = False
    pricing: dict[str, Any] | None = None
    network: str | None = None


class Invoice(BaseModel):
    id: str
    run_id: str
    user_id: str
    org_id: str
    tokens_in: int = 0
    tokens_out: int = 0
    tool_calls: int = 0
    cost_usdc: int = 0
    created_at: datetime | None = None


class CreditHistoryEntry(BaseModel):
    id: str
    org_id: str
    operation: str
    amount_usdc: int
    balance_usdc_after: int
    reason: str = ""
    created_at: datetime | None = None


# ─── Usage ────────────────────────────────────────────────────────────────────


class UsageSummary(BaseModel):
    total_runs: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_tool_calls: int = 0
    total_duration_ms: int = 0


# ─── Wallets ──────────────────────────────────────────────────────────────────


class Wallet(BaseModel):
    id: str
    address: str
    chain_id: int
    user_id: str
    org_id: str
    is_primary: bool = False
    created_at: datetime | None = None


# ─── Agent Card ───────────────────────────────────────────────────────────────


class AgentCard(BaseModel):
    """Minimal representation of the A2A agent card.

    Unknown fields from the API are preserved via ``model_extra``.
    """

    name: str = ""
    description: str = ""
    url: str = ""
    skills: list[dict[str, Any]] = Field(default_factory=list)


# ─── Custom Tools ─────────────────────────────────────────────────────────────


class CreateCustomToolRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str = Field(..., min_length=1, max_length=500)
    input_schema: dict[str, Any] = Field(...)
    webhook_url: str = Field(..., max_length=2048)
    webhook_method: str = Field(default="POST")
    auth_header_name: str | None = Field(default=None, max_length=64)
    auth_header_value: str | None = Field(default=None, max_length=4096)
    timeout_seconds: int = Field(default=10, ge=1, le=30)


class CustomTool(BaseModel):
    id: str
    org_id: str
    name: str
    description: str
    input_schema: dict[str, Any]
    webhook_url: str
    webhook_method: str
    has_auth: bool
    timeout_seconds: int
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"extra": "allow"}
