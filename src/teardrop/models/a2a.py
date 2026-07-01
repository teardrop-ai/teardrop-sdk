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
