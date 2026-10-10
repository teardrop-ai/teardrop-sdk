"""Tests for the public scorecard client module."""

from __future__ import annotations

from teardrop.models import (
    LeaderboardResponse,
    ScorecardItem,
    ScorecardResponse,
    ScorecardTaskListResponse,
)

from .conftest import _json_response

_ITEM = {
    "subject": "schedule:run-1",
    "platform_attested": False,
    "eligible": False,
    "n_scored": 0,
    "rounds_submitted": 1,
    "rounds_expected": 10,
    "coverage": None,
    "unresolved": 1,
    "mean_brier": None,
    "adjusted_brier": None,
    "accuracy": None,
    "calibration": None,
}


def test_scorecard_calibration_is_optional_but_other_metrics_remain_required():
    assert not ScorecardItem.model_fields["calibration"].is_required()
    assert ScorecardItem.model_fields["calibration"].default is None
    required_fields = {
        "subject",
        "platform_attested",
        "eligible",
        "n_scored",
        "rounds_submitted",
        "rounds_expected",
        "coverage",
        "unresolved",
        "mean_brier",
        "adjusted_brier",
        "accuracy",
    }
    assert all(ScorecardItem.model_fields[name].is_required() for name in required_fields)


class TestScorecardTasks:
    async def test_list_tasks_parses_task_envelope(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {
                "items": [
                    {
                        "definition_key": "quality.v1",
                        "definition_version": 2,
                        "definition_sha256": "a" * 64,
                        "prediction_schema": {"type": "object"},
                        "config": {"min_sample": 10},
                    }
                ]
            }
        )

        result = await client.scorecards.list_tasks()

        assert isinstance(result, ScorecardTaskListResponse)
        assert result.items[0].definition_version == 2
        assert mock_http.get.call_args.args[0] == "http://test/scorecards/tasks"
        assert mock_http.get.call_args.kwargs == {}


class TestScorecardResults:
    async def test_get_leaderboard_forwards_version_and_window(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {
                "definition_key": "quality.v1",
                "definition_version": 2,
                "definition_sha256": "a" * 64,
                "window_days": 30,
                "min_sample": 10,
                "items": [_ITEM],
            }
        )

        result = await client.scorecards.get_leaderboard("quality.v1", 2, window_days=30)

        assert isinstance(result, LeaderboardResponse)
        assert result.items[0].adjusted_brier is None
        assert result.items[0].calibration is None
        assert mock_http.get.call_args.args[0] == "http://test/scorecards/quality.v1/2"
        assert mock_http.get.call_args.kwargs["params"] == {"window_days": 30}

    async def test_get_scorecard_quotes_subject(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {
                "definition_key": "quality.v1",
                "definition_version": 2,
                "definition_sha256": "a" * 64,
                "window_days": 90,
                "min_sample": 10,
                "item": _ITEM,
            }
        )

        result = await client.scorecards.get_scorecard("quality.v1", 2, "schedule:run-1")

        assert isinstance(result, ScorecardResponse)
        assert result.item.eligible is False
        assert (
            mock_http.get.call_args.args[0]
            == "http://test/scorecards/quality.v1/2/schedule%3Arun-1"
        )
        assert mock_http.get.call_args.kwargs["params"] == {"window_days": 90}
