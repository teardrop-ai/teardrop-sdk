"""Tests for AsyncTeardropClient event triggers module methods."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from teardrop.exceptions import NotFoundError
from teardrop.models import (
    CreateEventTriggerRequest,
    EventTrigger,
    EventTriggerWithSecret,
    ScheduledRunResult,
    ScheduledRunsPage,
    UpdateEventTriggerRequest,
)

from .conftest import _json_response

_TRIGGER = {
    "id": "evt-trigger-uuid",
    "org_id": "test-org-id",
    "user_id": "test-user-id",
    "name": "On Payment Inbound",
    "prompt": "Audit incoming payment of {{amount}} for user {{userId}}. Full tx: {{event_json}}",
    "schedule_kind": "event",
    "enabled": True,
    "callback_url": "https://callback.domain.com/hook",
    "trigger_token": "H3_public_route_token",
    "event_path": "/agent/events/H3_public_route_token",
    "consecutive_failures": 0,
    "last_run_at": None,
    "created_at": "2026-06-28T12:00:00Z",
    "updated_at": "2026-06-28T12:00:00Z",
}

_TRIGGER_WITH_SECRET = {
    **_TRIGGER,
    "secret": "high_entropy_signing_secret_here",
}

_RUN_RESULT = {
    "id": "result-uuid",
    "schedule_id": _TRIGGER["id"],
    "org_id": "test-org-id",
    "run_id": "background-execution-run-id",
    "status": "completed",
    "output_text": "Payment audited successfully",
    "cost_usdc": 15000,
    "error": "",
    "created_at": "2026-06-28T12:00:25Z",
}

_RUN_RESULT_2 = {
    **_RUN_RESULT,
    "id": "result-uuid-2",
    "run_id": "background-execution-run-id-2",
}


class TestEventTriggersCreate:
    async def test_returns_trigger_with_secret(self, client, mock_http):
        mock_http.post.return_value = _json_response(_TRIGGER_WITH_SECRET)

        result = await client.event_triggers.create(
            CreateEventTriggerRequest(
                name="On Payment Inbound",
                prompt="Audit incoming payment of {{amount}} for user {{userId}}.",
                callback_url="https://callback.domain.com/hook",
            )
        )

        assert isinstance(result, EventTriggerWithSecret)
        assert result.secret == "high_entropy_signing_secret_here"


class TestEventTriggerRequestValidation:
    def test_create_rejects_non_https_callback_url(self):
        with pytest.raises(ValidationError):
            CreateEventTriggerRequest(
                name="On Payment Inbound",
                prompt="Audit incoming payment",
                callback_url="http://callback.domain.com/hook",
            )

    def test_update_rejects_non_https_callback_url(self):
        with pytest.raises(ValidationError):
            UpdateEventTriggerRequest(callback_url="http://callback.domain.com/hook")


class TestEventTriggersList:
    async def test_returns_trigger_list_even_when_route_fields_are_hidden(self, client, mock_http):
        trigger = {
            key: value
            for key, value in _TRIGGER.items()
            if key not in {"trigger_token", "event_path"}
        }
        mock_http.get.return_value = _json_response([trigger])

        result = await client.event_triggers.list()

        assert len(result) == 1
        assert isinstance(result[0], EventTrigger)
        assert result[0].trigger_token is None
        assert result[0].event_path is None


class TestEventTriggersGet:
    async def test_returns_trigger(self, client, mock_http):
        mock_http.get.return_value = _json_response(_TRIGGER)

        result = await client.event_triggers.get(_TRIGGER["id"])

        assert isinstance(result, EventTrigger)
        assert result.event_path == "/agent/events/H3_public_route_token"

    async def test_404_raises_not_found(self, client, mock_http):
        mock_http.get.return_value = _json_response({"detail": "Not found"}, status=404)

        with pytest.raises(NotFoundError):
            await client.event_triggers.get("missing")


class TestEventTriggersUpdate:
    async def test_partial_update_forwards_only_set_fields(self, client, mock_http):
        updated = {**_TRIGGER, "enabled": False, "callback_url": None}
        mock_http.patch.return_value = _json_response(updated)

        result = await client.event_triggers.update(
            _TRIGGER["id"],
            UpdateEventTriggerRequest(enabled=False, callback_url=None),
        )

        _, kwargs = mock_http.patch.call_args
        assert kwargs["json"] == {"enabled": False, "callback_url": None}
        assert isinstance(result, EventTrigger)
        assert result.enabled is False


class TestEventTriggersDelete:
    async def test_returns_none(self, client, mock_http):
        mock_http.delete.return_value = _json_response({}, status=204)

        result = await client.event_triggers.delete(_TRIGGER["id"])

        assert result is None


class TestEventTriggersRotateSecret:
    async def test_returns_plain_secret_payload(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {"id": _TRIGGER["id"], "secret": "rotated_secret_value"}
        )

        result = await client.event_triggers.rotate_secret(_TRIGGER["id"])

        assert result == {"id": _TRIGGER["id"], "secret": "rotated_secret_value"}


class TestEventTriggersRuns:
    async def test_returns_paginated_runs(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {"items": [_RUN_RESULT], "next_cursor": "2026-06-28T12:00:25Z"}
        )

        result = await client.event_triggers.runs(_TRIGGER["id"], limit=5, cursor="page-2")

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
            async for item in client.event_triggers.runs_iter(
                _TRIGGER["id"],
                limit=1,
            )
        ]

        assert [item.id for item in items] == ["result-uuid", "result-uuid-2"]
        first_call = mock_http.get.call_args_list[0]
        second_call = mock_http.get.call_args_list[1]
        assert first_call.kwargs["params"] == {"limit": 1}
        assert second_call.kwargs["params"] == {"limit": 1, "cursor": "page-2"}
