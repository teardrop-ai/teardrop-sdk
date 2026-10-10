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


class PredictionSubmitRequest(BaseModel):
    """Signed external prediction submission; the server assigns its timestamp."""

    definition_key: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,127}$")
    definition_version: int = Field(gt=0)
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9._:-]{1,128}$")
    signer_address: str = Field(pattern=r"^0x[0-9a-fA-F]{40}$")
    signature: str = Field(pattern=r"^0x[0-9a-fA-F]{130}$")
    predictions: dict[str, Any]

    model_config = {"extra": "forbid"}


class PredictionSubmitResponse(BaseModel):
    """Result body for a newly accepted prediction submission."""

    id: str
    payload_sha256: str
    status: Literal["accepted"]
    created: bool


class PredictionProofAnchor(BaseModel):
    """Merkle-batch commitment and optional chain-anchor metadata."""

    batch_id: str
    leaf_index: int
    tree_size: int
    merkle_root: str
    audit_path: list[str]
    chain_id: int
    tx_hash: str | None
    anchor_address: str | None
    block_number: int | None
    anchored_at: str | None


class PredictionProofResponse(BaseModel):
    """Prediction commitment proof, with an anchor once the batch is sealed."""

    prediction_id: str
    status: Literal["pending", "submitted", "anchored"]
    hash_algorithm: Literal["rfc6962-sha256"]
    leaf_version: int
    leaf_preimage: dict[str, Any]
    salt: str
    leaf_sha256: str
    anchor: PredictionProofAnchor | None


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
