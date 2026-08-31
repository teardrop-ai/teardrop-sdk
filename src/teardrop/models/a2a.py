"""A2A delegation models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AddTrustedAgentRequest(BaseModel):
    agent_url: str
    label: str | None = None
    max_cost_usdc: int | None = None
    require_x402: bool = False
    jwt_forward: bool = False


class TrustedAgent(BaseModel):
    id: str
    org_id: str
    agent_url: str
    label: str | None = None
    max_cost_usdc: int
    require_x402: bool
    jwt_forward: bool
    created_at: str | None = None

    model_config = {"extra": "allow"}


A2AAgentResponse = TrustedAgent
OrgA2AAgentResponse = TrustedAgent


class A2AAgentListItem(TrustedAgent):
    """Item returned by GET /a2a/agents and /admin/a2a/agents/{org_id}."""


class OrgA2AAgentListItem(A2AAgentListItem):
    """Item returned by GET /a2a/agents (org-scoped; spec omits org_id here)."""

    org_id: str = ""


class A2AAgentDeletedResponse(BaseModel):
    """Response from DELETE /a2a/agents/{agent_id} and admin variant."""

    deleted: str


OrgA2AAgentDeletedResponse = A2AAgentDeletedResponse


class A2ADelegationEvent(BaseModel):
    """Event returned by GET /a2a/delegations."""

    id: str
    run_id: str
    agent_url: str
    task_status: str
    task_type: str
    cost_usdc: int
    billing_method: str
    agent_name: str | None = None
    created_at: str | None = None
    error: str | None = None
    settlement_tx: str | None = None
    delivery_status: str = "not_attempted"
    delivery_error: str | None = None
    delivery_resolved_at: str | None = None
    delivery_settlement_tx: str | None = None

    model_config = {"extra": "allow"}


class PossiblyDeliveredDelegationItem(BaseModel):
    """Item returned by GET /admin/a2a/delegations/possibly-delivered."""

    id: str
    org_id: str
    run_id: str
    amount_usdc: int
    delivery_status: str
    refund_status: str
    agent_name: str | None = None
    agent_url: str | None = None
    billing_method: str | None = None
    created_at: str | None = None
    delivery_error: str | None = None
    delivery_settlement_tx: str | None = None
    delivery_started_at: str | None = None
    settlement_tx: str | None = None
    task_status: str | None = None
    task_type: str | None = None

    model_config = {"extra": "allow"}


class ResolveA2ADelegationRequest(BaseModel):
    """Request body for POST /admin/a2a/delegations/{delegation_id}/resolve."""

    org_id: str = Field(min_length=1, max_length=200)
    outcome: Literal["confirmed", "failed"]
    reason: str = Field(default="", max_length=500)
    settlement_tx: str | None = Field(
        default=None,
        max_length=66,
        pattern=r"^0x[a-fA-F0-9]{64}$",
    )


class ResolveA2ADelegationResponse(BaseModel):
    """Response from POST /admin/a2a/delegations/{delegation_id}/resolve."""

    id: str
    org_id: str
    outcome: Literal["confirmed", "failed"]
    refund_status: Literal["cancelled", "refunded"]

    model_config = {"extra": "allow"}
