"""Tests for AsyncTeardropClient schedules module methods."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from teardrop.exceptions import NotFoundError
from teardrop.models import (
    CreateScheduleRequest,
    ScheduledRun,
    ScheduledRunResult,
    ScheduledRunsPage,
    UpdateScheduleRequest,
)

from .conftest import _json_response

_SCHEDULE = {
    "id": "7f09315d-85fa-42f2-b43a-7db0df95d321",
    "org_id": "test-org-id",
    "user_id": "test-user-id",
    "name": "Daily Summary",
    "prompt": "Summarize portfolio balances",
    "schedule_kind": "interval",
    "interval_seconds": 86400,
    "enabled": True,
    "callback_url": "https://callback.domain.com/hook",
    "next_run_at": "2026-06-29T12:00:00Z",
    "last_run_at": "2026-06-28T12:00:00Z",
    "consecutive_failures": 0,
    "created_at": "2026-06-28T11:00:00Z",
    "updated_at": "2026-06-28T11:00:00Z",
}

_RUN_RESULT = {
    "id": "result-uuid",
    "schedule_id": _SCHEDULE["id"],
    "org_id": "test-org-id",
    "run_id": "core-thread-run-id",
    "status": "completed",
    "output_text": "Portfolio yields stable...",
    "cost_usdc": 15000,
    "error": "",
    "created_at": "2026-06-28T12:00:25Z",
}

_RUN_RESULT_2 = {
    **_RUN_RESULT,
    "id": "result-uuid-2",
    "run_id": "core-thread-run-id-2",
}


class TestSchedulesCreate:
    async def test_returns_scheduled_run(self, client, mock_http):
        mock_http.post.return_value = _json_response(_SCHEDULE)

        result = await client.schedules.create(
            CreateScheduleRequest(
                name="Daily Summary",
                prompt="Summarize portfolio balances",
                interval_seconds=86400,
                callback_url="https://callback.domain.com/hook",
            )
        )

        assert isinstance(result, ScheduledRun)
        assert result.id == _SCHEDULE["id"]

    async def test_correct_url_and_body(self, client, mock_http):
        mock_http.post.return_value = _json_response(_SCHEDULE)

        await client.schedules.create(
            CreateScheduleRequest(
                name="Daily Summary",
                prompt="Summarize portfolio balances",
                interval_seconds=86400,
            )
        )

        args, kwargs = mock_http.post.call_args
        assert args[0] == "http://test/agent/schedules"
        assert kwargs["json"] == {
            "name": "Daily Summary",
            "prompt": "Summarize portfolio balances",
            "interval_seconds": 86400,
        }


class TestScheduleRequestValidation:
    def test_create_rejects_non_https_callback_url(self):
        with pytest.raises(ValidationError):
            CreateScheduleRequest(
                name="Daily Summary",
                prompt="Summarize portfolio balances",
                interval_seconds=86400,
                callback_url="http://callback.domain.com/hook",
            )

    def test_create_rejects_interval_below_minimum(self):
        with pytest.raises(ValidationError):
            CreateScheduleRequest(
                name="Daily Summary",
                prompt="Summarize portfolio balances",
                interval_seconds=0,
            )

    def test_update_rejects_interval_below_minimum(self):
        with pytest.raises(ValidationError):
            UpdateScheduleRequest(interval_seconds=0)


class TestSchedulesList:
    async def test_returns_schedule_list(self, client, mock_http):
        mock_http.get.return_value = _json_response([_SCHEDULE])

        result = await client.schedules.list()

        assert len(result) == 1
        assert isinstance(result[0], ScheduledRun)
        assert result[0].name == "Daily Summary"


class TestSchedulesGet:
    async def test_returns_schedule(self, client, mock_http):
        mock_http.get.return_value = _json_response(_SCHEDULE)

        result = await client.schedules.get(_SCHEDULE["id"])

        assert isinstance(result, ScheduledRun)
        assert result.interval_seconds == 86400

    async def test_404_raises_not_found(self, client, mock_http):
        mock_http.get.return_value = _json_response({"detail": "Not found"}, status=404)

        with pytest.raises(NotFoundError):
            await client.schedules.get("missing")


class TestSchedulesUpdate:
    async def test_partial_update_forwards_only_set_fields(self, client, mock_http):
        updated = {**_SCHEDULE, "enabled": False, "callback_url": None}
        mock_http.patch.return_value = _json_response(updated)

        result = await client.schedules.update(
            _SCHEDULE["id"],
            UpdateScheduleRequest(enabled=False, callback_url=None),
        )

        _, kwargs = mock_http.patch.call_args
        assert kwargs["json"] == {"enabled": False, "callback_url": None}
        assert isinstance(result, ScheduledRun)
        assert result.enabled is False
        assert result.callback_url is None


class TestSchedulesDelete:
    async def test_returns_none(self, client, mock_http):
        mock_http.delete.return_value = _json_response({}, status=204)

        result = await client.schedules.delete(_SCHEDULE["id"])

        assert result is None


class TestSchedulesRuns:
    async def test_returns_paginated_runs(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {"items": [_RUN_RESULT], "next_cursor": "2026-06-28T12:00:25Z"}
        )

        result = await client.schedules.runs(_SCHEDULE["id"], limit=5, cursor="page-2")

        _, kwargs = mock_http.get.call_args
        assert kwargs["params"] == {"limit": 5, "cursor": "page-2"}
        assert isinstance(result, ScheduledRunsPage)
        assert isinstance(result.items[0], ScheduledRunResult)
        assert result.next_cursor == "2026-06-28T12:00:25Z"

    async def test_runs_iter_auto_paginates_until_cursor_exhausted(self, client, mock_http):
        mock_http.get.side_effect = [
            _json_response({"items": [_RUN_RESULT], "next_cursor": "page-2"}),
            _json_response({"items": [_RUN_RESULT_2], "next_cursor": None}),
        ]

        items = [
            item
            async for item in client.schedules.runs_iter(
                _SCHEDULE["id"],
                limit=1,
            )
        ]

        assert [item.id for item in items] == ["result-uuid", "result-uuid-2"]
        first_call = mock_http.get.call_args_list[0]
        second_call = mock_http.get.call_args_list[1]
        assert first_call.kwargs["params"] == {"limit": 1}
        assert second_call.kwargs["params"] == {"limit": 1, "cursor": "page-2"}
