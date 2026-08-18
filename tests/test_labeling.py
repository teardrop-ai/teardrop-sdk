"""Tests for the org-scoped labeling client module."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from teardrop.models import (
    LabelingBindingRequest,
    LabelingBindingResponse,
    LabelingDefinitionListResponse,
    LabelingOverrideResponse,
    LabelingPredictionListResponse,
    LabelingResultListResponse,
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
