"""Tests for the org-scoped labeling client module."""

from __future__ import annotations

import httpx
import pytest
from pydantic import ValidationError

from teardrop.exceptions import ConflictError
from teardrop.models import (
    LabelingBindingRequest,
    LabelingBindingResponse,
    LabelingDefinitionListResponse,
    LabelingOverrideResponse,
    LabelingPredictionListResponse,
    LabelingResultListResponse,
    PredictionProofResponse,
    PredictionSubmitRequest,
    PredictionSubmitResponse,
    ScoreResult,
)

from .conftest import _json_response

_DEFINITION = {
    "definition_key": "quality-v1",
    "definition_version": 1,
    "prediction_schema": {"type": "object"},
    "target_schema": {"type": "object"},
    "outcome_schema": {"type": "object"},
    "active": True,
    "created_at": "2026-08-17T12:00:00Z",
}

_PREDICTION = {
    "id": "prediction-1",
    "source_kind": "schedule",
    "source_id": "schedule-1",
    "run_id": "run-1",
    "schedule_id": "schedule-1",
    "definition_key": "quality-v1",
    "definition_version": 1,
    "predictions": {"label": "good"},
    "payload_sha256": "a" * 64,
    "prediction_at": "2026-08-17T12:00:00Z",
    "status": "parsed",
    "parse_error": "",
    "created_at": "2026-08-17T12:00:00Z",
}

_RESULT = {
    "id": "result-1",
    "target_id": "target-1",
    "scorer_key": "quality",
    "scorer_version": "1",
    "observation_id": None,
    "actual": None,
    "label": "good",
    "score": 1.0,
    "status": "correct",
    "source": "automatic",
    "rationale": "Matched expected outcome",
    "created_at": "2026-08-17T12:00:00Z",
}


class TestLabelingDefinitions:
    async def test_get_definitions_returns_typed_response(self, client, mock_http):
        mock_http.get.return_value = _json_response({"items": [_DEFINITION]})

        result = await client.labeling.get_definitions()

        assert isinstance(result, LabelingDefinitionListResponse)
        assert result.items[0].definition_key == "quality-v1"
        assert mock_http.get.call_args.args[0] == "http://test/labeling/definitions"


class TestLabelingPredictions:
    async def test_get_predictions_forwards_limit(self, client, mock_http):
        mock_http.get.return_value = _json_response({"items": [_PREDICTION]})

        result = await client.labeling.get_predictions(limit=10)

        assert isinstance(result, LabelingPredictionListResponse)
        assert result.items[0].parse_error == ""
        assert mock_http.get.call_args.kwargs["params"] == {"limit": 10}

    async def test_submit_prediction_returns_body_for_new_submission(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {
                "id": "prediction-2",
                "payload_sha256": "b" * 64,
                "status": "accepted",
                "created": True,
            },
            status=201,
        )
        request = PredictionSubmitRequest(
            definition_key="quality-v1",
            definition_version=1,
            idempotency_key="client-request-1",
            signer_address="0x" + "1" * 40,
            signature="0x" + "a" * 130,
            predictions={"label": "good"},
        )

        result = await client.labeling.submit_prediction(request)

        assert isinstance(result, PredictionSubmitResponse)
        assert result.created is True
        assert mock_http.post.call_args.args[0] == "http://test/labeling/predictions"
        assert mock_http.post.call_args.kwargs["json"] == request.model_dump()

    async def test_submit_prediction_returns_none_for_bodyless_idempotent_replay(
        self, client, mock_http
    ):
        mock_http.post.return_value = httpx.Response(
            status_code=200,
            content=b"",
            request=httpx.Request("POST", "http://test/labeling/predictions"),
        )
        request = PredictionSubmitRequest(
            definition_key="quality-v1",
            definition_version=1,
            idempotency_key="client-request-1",
            signer_address="0x" + "1" * 40,
            signature="0x" + "a" * 130,
            predictions={"label": "good"},
        )

        result = await client.labeling.submit_prediction(request)

        assert result is None
        assert mock_http.post.call_args.args[0] == "http://test/labeling/predictions"

    async def test_submit_prediction_preserves_conflict_mapping(self, client, mock_http):
        mock_http.post.return_value = _json_response({"detail": "Idempotency key conflict"}, 409)
        request = PredictionSubmitRequest(
            definition_key="quality-v1",
            definition_version=1,
            idempotency_key="client-request-1",
            signer_address="0x" + "1" * 40,
            signature="0x" + "a" * 130,
            predictions={"label": "good"},
        )

        with pytest.raises(ConflictError):
            await client.labeling.submit_prediction(request)

    async def test_get_prediction_proof_quotes_id_and_accepts_unsealed_anchor(
        self, client, mock_http
    ):
        mock_http.get.return_value = _json_response(
            {
                "prediction_id": "pred/id 1",
                "status": "submitted",
                "hash_algorithm": "rfc6962-sha256",
                "leaf_version": 1,
                "leaf_preimage": {"id": "pred/id 1"},
                "salt": "salt",
                "leaf_sha256": "c" * 64,
                "anchor": None,
            }
        )

        result = await client.labeling.get_prediction_proof("pred/id 1")

        assert isinstance(result, PredictionProofResponse)
        assert result.anchor is None
        assert (
            mock_http.get.call_args.args[0]
            == "http://test/labeling/predictions/pred%2Fid%201/proof"
        )


class TestLabelingResults:
    async def test_get_results_returns_nullable_result_fields(self, client, mock_http):
        mock_http.get.return_value = _json_response({"items": [_RESULT]})

        result = await client.labeling.get_results()

        assert isinstance(result, LabelingResultListResponse)
        assert result.items[0].observation_id is None
        assert mock_http.get.call_args.kwargs["params"] == {"limit": 50}


class TestLabelingWrites:
    async def test_bind_definition_forwards_request(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {
                "id": "binding-1",
                "schedule_id": "schedule-1",
                "definition_key": "quality-v1",
                "definition_version": 1,
                "status": "created",
            },
            status=201,
        )
        request = LabelingBindingRequest(
            schedule_id="schedule-1",
            definition_key="quality-v1",
            definition_version=1,
        )

        result = await client.labeling.bind_definition(request)

        assert isinstance(result, LabelingBindingResponse)
        assert mock_http.post.call_args.args[0] == "http://test/labeling/bindings"
        assert mock_http.post.call_args.kwargs["json"] == request.model_dump()

    async def test_override_result_quotes_target_id(self, client, mock_http):
        mock_http.post.return_value = _json_response({"status": "recorded"}, status=201)
        request = ScoreResult(label="good", status="correct")

        result = await client.labeling.override_result("target/with space", request)

        assert isinstance(result, LabelingOverrideResponse)
        assert (
            mock_http.post.call_args.args[0]
            == "http://test/labeling/results/target%2Fwith%20space/override"
        )

    def test_score_result_enforces_spec_rationale_limit(self):
        with pytest.raises(ValidationError):
            ScoreResult(label="good", status="correct", rationale="x" * 2001)
