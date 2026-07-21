"""Telemetry and observability models for admin endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


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
