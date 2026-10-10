"""Public scorecard task and leaderboard models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class CalibrationBin(BaseModel):
    bin: int
    lower: float
    upper: float
    count: int
    mean_probability: float
    observed_frequency: float


class ScorecardItem(BaseModel):
    subject: str
    platform_attested: bool
    eligible: bool
    n_scored: int
    rounds_submitted: int
    rounds_expected: int
    coverage: float | None
    unresolved: int
    mean_brier: float | None
    adjusted_brier: float | None
    accuracy: float | None
    calibration: list[CalibrationBin] | None = None


class LeaderboardResponse(BaseModel):
    definition_key: str
    definition_version: int
    definition_sha256: str
    window_days: int
    min_sample: int
    items: list[ScorecardItem]


class ScorecardResponse(BaseModel):
    definition_key: str
    definition_version: int
    definition_sha256: str
    window_days: int
    min_sample: int
    item: ScorecardItem


class ScorecardTask(BaseModel):
    definition_key: str
    definition_version: int
    definition_sha256: str
    prediction_schema: dict[str, Any]
    config: dict[str, Any]


class ScorecardTaskListResponse(BaseModel):
    items: list[ScorecardTask]
