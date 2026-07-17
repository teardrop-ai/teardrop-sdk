"""A2A delegation models."""

from __future__ import annotations

from pydantic import BaseModel


class AddTrustedAgentRequest(BaseModel):
    agent_url: str
    label: str | None = None
    max_cost_usdc: int | None = None
    require_x402: bool = False
    jwt_forward: bool = False


class TrustedAgent(BaseModel):
    id: str
    org_id: str | None = None
    agent_url: str
    label: str | None = None
    max_cost_usdc: int = 0
    require_x402: bool = False
    jwt_forward: bool = False
    created_at: str | None = None

    model_config = {"extra": "allow"}


A2AAgentResponse = TrustedAgent
OrgA2AAgentResponse = TrustedAgent


class A2AAgentListItem(TrustedAgent):
    """Item returned by GET /a2a/agents and /admin/a2a/agents/{org_id}."""


class OrgA2AAgentListItem(A2AAgentListItem):
    """Alias matching the admin list schema name."""


class A2AAgentDeletedResponse(BaseModel):
    """Response from DELETE /a2a/agents/{agent_id} and admin variant."""

    id: str
    deleted_at: str = ""

    model_config = {"extra": "allow"}


OrgA2AAgentDeletedResponse = A2AAgentDeletedResponse


class A2ADelegationEvent(BaseModel):
    """Event returned by GET /a2a/delegations."""

    id: str
    agent_id: str
    task_id: str | None = None
    status: str = ""
    created_at: str = ""

    model_config = {"extra": "allow"}
