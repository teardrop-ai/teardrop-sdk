"""Admin-only request/response models matching spec/openapi.json admin schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

# ── Admin A2A ─────────────────────────────────────────────────────────────────


class AdminCreateA2AAgentRequest(BaseModel):
    """Request body for POST /admin/a2a/agents."""

    org_id: str
    agent_url: str = Field(..., min_length=10, max_length=2000)
    label: str | None = Field(default=None, max_length=200)
    max_cost_usdc: int = Field(
        default=0, description="Per-delegation cost cap in atomic USDC (0 = global default)."
    )
    require_x402: bool = Field(default=False, description="Require x402 payment for this agent.")
    jwt_forward: bool = Field(
        default=False, description="Forward caller JWT as Authorization header to this agent."
    )


# ── Admin Identity ────────────────────────────────────────────────────────────


class AdminCreateClientCredentialsRequest(BaseModel):
    """Request body for POST /admin/client-credentials."""

    org_id: str


class AdminCreateOrgRequest(BaseModel):
    """Request body for POST /admin/orgs."""

    name: str = Field(..., min_length=1, max_length=200)


class AdminCreateUserRequest(BaseModel):
    """Request body for POST /admin/users."""

    email: str = Field(..., min_length=3, max_length=320)
    secret: str = Field(..., min_length=8, max_length=128)
    org_id: str
    role: str = "user"


# ── Admin Billing ─────────────────────────────────────────────────────────────


class AdminTopupRequest(BaseModel):
    """Request body for POST /admin/credits/topup."""

    org_id: str
    amount_usdc: int = Field(..., gt=0)


class SpendingConfigUpdate(BaseModel):
    """Request body for PATCH /admin/orgs/{org_id}/spending."""

    spending_limit_usdc: int | None = None
    is_paused: bool | None = None


class ToolPricingOverrideRequest(BaseModel):
    """Request body for POST /admin/pricing/tools."""

    tool_name: str = Field(..., min_length=1, max_length=100)
    cost_usdc: int = Field(..., ge=0, le=100_000_000)
    description: str = Field(default="", max_length=500)


# ── Admin Marketplace ─────────────────────────────────────────────────────────


class CompleteWithdrawalRequest(BaseModel):
    """Request body for POST /admin/marketplace/complete-withdrawal/{withdrawal_id}."""

    tx_hash: str = Field(..., min_length=10, max_length=100)
