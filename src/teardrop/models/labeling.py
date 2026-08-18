"""Org-scoped labeling models and scoring payloads."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class LabelingBindingRequest(BaseModel):
    schedule_id: str = Field(..., min_length=1, max_length=256)
    definition_key: str = Field(..., min_length=1, max_length=128)
    definition_version: int = Field(..., gt=0)


class LabelingBindingResponse(BaseModel):
    id: str
    schedule_id: str
    definition_key: str
    definition_version: int
    status: Literal["created"]


class LabelingDefinitionItem(BaseModel):
    definition_key: str
    definition_version: int
    prediction_schema: dict[str, Any]
    target_schema: dict[str, Any]
    outcome_schema: dict[str, Any]
    active: bool
    created_at: str


class LabelingDefinitionListResponse(BaseModel):
    items: list[LabelingDefinitionItem]


class LabelingPredictionItem(BaseModel):
    id: str
    source_kind: str
    source_id: str
    run_id: str
    schedule_id: str
    definition_key: str
    definition_version: int
    predictions: dict[str, Any]
    payload_sha256: str
    prediction_at: str
    status: str
    parse_error: str
    created_at: str


class LabelingPredictionListResponse(BaseModel):
    items: list[LabelingPredictionItem]


class LabelingResultItem(BaseModel):
    id: str
    target_id: str
    scorer_key: str
    scorer_version: str
    observation_id: str | None
    actual: dict[str, Any] | None
    label: str
    score: float | None
    status: str
    source: str
    rationale: str
    created_at: str


class LabelingResultListResponse(BaseModel):
    items: list[LabelingResultItem]


class LabelingOverrideResponse(BaseModel):
    status: Literal["recorded"]


class ScoreResult(BaseModel):
    label: str = Field(..., min_length=1, max_length=128)
    actual: dict[str, Any] | None = None
    score: float | None = None
    rationale: str = Field(default="", max_length=2000)
    source: Literal["automatic", "external", "manual"] = "automatic"
    status: Literal["correct", "incorrect", "neutral", "inconclusive", "unavailable", "invalid"]

    model_config = {"extra": "forbid"}
