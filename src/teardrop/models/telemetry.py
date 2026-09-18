"""Telemetry and observability models for admin endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TelemetryCompletenessBySource(BaseModel):
    """Telemetry coverage metrics for a single execution source."""

    model_config = {"extra": "allow"}

    source: Literal["api", "schedule", "trigger", "a2a"]
    decision_coverage: float = 0.0
    outcome_label_coverage: float = 0.0
    tool_eligible_runs: int = 0
    tool_event_coverage: float | None = None
    total_runs: int = 0
    usage_event_coverage: float = 0.0


class TelemetryCompletenessResponse(BaseModel):
    """Aggregate telemetry completeness response across all execution sources."""

    model_config = {"extra": "allow"}

    window_days: int
    sources: list[TelemetryCompletenessBySource]


class DiscoveryStageDay(BaseModel):
    """One day of per-stage discovery hit counts (UTC day bucket)."""

    model_config = {"extra": "allow"}

    date: str
    agent_card_hits: int = 0
    catalog_hits: int = 0
    mcp_402_challenges: int = 0
    mcp_server_card_hits: int = 0
    quote_hits: int = 0
    settled_calls: int = 0
    tools_list_hits: int = 0
    x402_discovery_hits: int = 0


class DiscoveryFunnelResponse(BaseModel):
    """Aggregate discovery-stage hit counts plus challenge-to-settle conversion."""

    model_config = {"extra": "allow"}

    window_days: int
    agent_card_hits: int = 0
    catalog_hits: int = 0
    challenge_to_settle_rate: float | None = None
    mcp_402_challenges: int = 0
    mcp_server_card_hits: int = 0
    quote_hits: int = 0
    series: list[DiscoveryStageDay] = Field(default_factory=list)
    settled_calls: int = 0
    tools_list_hits: int = 0
    x402_discovery_hits: int = 0


class MachineFunnelResponse(BaseModel):
    """Machine-org funnel: provisioning, settlement, and payer conversion."""

    model_config = {"extra": "allow"}

    anonymous_settled_calls: int = 0
    converted_payers: int = 0
    failed_calls: int = 0
    machine_orgs_provisioned: int = 0
    org_bound_settled_calls: int = 0
    repeat_payer_gate: bool = False
    repeat_payer_rate: float | None = None
    repeat_payers: int = 0
    settled_calls: int = 0
    settled_revenue_usdc: int = 0
    settlement_attempts: int = 0
    settlement_failure_rate: float | None = None
    siwe_orgs_provisioned: int = 0
    unique_anonymous_payers: int = 0
    wallet_conversion_rate: float | None = None
    window_days: int
    x402_orgs_provisioned: int = 0
