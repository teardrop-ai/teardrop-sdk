"""Tests for AsyncTeardropClient event triggers module methods."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from teardrop.exceptions import NotFoundError
from teardrop.models import (
    CreateEventTriggerRequest,
    EventRunResultItem,
    EventRunResultsResponse,
    EventTaskResponse,
    EventTrigger,
    EventTriggerListResponse,
    EventTriggerWithSecret,
    RotateSecretResponse,
    ScheduleDeletedResponse,
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
    "next_trigger_id": "evt-trigger-next",
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
    "chain_id": "event-chain-1",
    "hop_index": 2,
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
                next_trigger_id=_TRIGGER["next_trigger_id"],
            )
        )

        _, kwargs = mock_http.post.call_args
        assert kwargs["json"] == {
            "name": "On Payment Inbound",
            "prompt": "Audit incoming payment of {{amount}} for user {{userId}}.",
            "callback_url": "https://callback.domain.com/hook",
            "next_trigger_id": "evt-trigger-next",
        }
        assert isinstance(result, EventTriggerWithSecret)
        assert result.secret == "high_entropy_signing_secret_here"
        assert result.next_trigger_id == _TRIGGER["next_trigger_id"]

    async def test_omits_unset_next_trigger_id(self, client, mock_http):
        response = {
            key: value for key, value in _TRIGGER_WITH_SECRET.items() if key != "next_trigger_id"
        }
        mock_http.post.return_value = _json_response(response)

        result = await client.event_triggers.create(
            CreateEventTriggerRequest(name="Trigger", prompt="Run task")
        )

        assert mock_http.post.call_args.kwargs["json"] == {
            "name": "Trigger",
            "prompt": "Run task",
        }
        assert result.next_trigger_id is None


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
        mock_http.get.return_value = _json_response({"items": [trigger], "next_cursor": None})

        result = await client.event_triggers.list()

        assert isinstance(result, EventTriggerListResponse)
        assert len(result.items) == 1
        assert isinstance(result.items[0], EventTrigger)
        assert result.items[0].trigger_token is None
        assert result.items[0].event_path is None


class TestEventTriggersGet:
    async def test_returns_trigger(self, client, mock_http):
        mock_http.get.return_value = _json_response(_TRIGGER)

        result = await client.event_triggers.get(_TRIGGER["id"])

        assert isinstance(result, EventTrigger)
        assert result.event_path == "/agent/events/H3_public_route_token"
        assert result.next_trigger_id == _TRIGGER["next_trigger_id"]

    async def test_404_raises_not_found(self, client, mock_http):
        mock_http.get.return_value = _json_response({"detail": "Not found"}, status=404)

        with pytest.raises(NotFoundError):
            await client.event_triggers.get("missing")


class TestEventTriggersUpdate:
    async def test_partial_update_forwards_only_set_fields(self, client, mock_http):
        updated = {
            **_TRIGGER,
            "enabled": False,
            "callback_url": None,
            "next_trigger_id": "evt-trigger-next-2",
        }
        mock_http.patch.return_value = _json_response(updated)

        result = await client.event_triggers.update(
            _TRIGGER["id"],
            UpdateEventTriggerRequest(
                enabled=False,
                callback_url=None,
                next_trigger_id="evt-trigger-next-2",
            ),
        )

        _, kwargs = mock_http.patch.call_args
        assert kwargs["json"] == {
            "enabled": False,
            "callback_url": None,
            "next_trigger_id": "evt-trigger-next-2",
        }
        assert isinstance(result, EventTrigger)
        assert result.enabled is False
        assert result.next_trigger_id == "evt-trigger-next-2"

    @pytest.mark.parametrize("clear_link", [False, True])
    async def test_omitted_and_explicit_null_link_are_distinct(self, client, mock_http, clear_link):
        updated = {**_TRIGGER, "enabled": False}
        request = UpdateEventTriggerRequest(enabled=False)
        expected: dict[str, bool | None] = {"enabled": False}
        if clear_link:
            updated["next_trigger_id"] = None
            request = UpdateEventTriggerRequest(enabled=False, next_trigger_id=None)
            expected["next_trigger_id"] = None
        mock_http.patch.return_value = _json_response(updated)

        result = await client.event_triggers.update(_TRIGGER["id"], request)

        assert mock_http.patch.call_args.kwargs["json"] == expected
        assert result.next_trigger_id == updated["next_trigger_id"]


class TestEventTriggersDelete:
    async def test_returns_deleted_response(self, client, mock_http):
        mock_http.delete.return_value = _json_response(
            {
                "id": _TRIGGER["id"],
                "status": "deleted",
                "deleted_at": "2026-01-01T00:00:00Z",
            }
        )

        result = await client.event_triggers.delete(_TRIGGER["id"])

        assert isinstance(result, ScheduleDeletedResponse)
        assert result.id == _TRIGGER["id"]


class TestEventTriggersRotateSecret:
    async def test_returns_rotate_secret_response(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {
                "id": _TRIGGER["id"],
                "secret": "rotated_secret_value",
                "rotated_at": "2026-01-01T00:00:00Z",
            }
        )

        result = await client.event_triggers.rotate_secret(_TRIGGER["id"])

        assert isinstance(result, RotateSecretResponse)
        assert result.id == _TRIGGER["id"]
        assert result.secret == "rotated_secret_value"


class TestEventTriggersGetRun:
    async def test_returns_event_task_response(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {
                "id": "task-1",
                "contextId": "ctx-1",
                "status": {"state": "TASK_STATE_COMPLETED", "timestamp": "2026-06-28T12:00:00Z"},
                "artifacts": [
                    {
                        "artifactId": "art-1",
                        "name": "result",
                        "parts": [{"text": "ok"}],
                    }
                ],
            }
        )

        result = await client.event_triggers.get_run(_TRIGGER["id"], "run-1")

        assert isinstance(result, EventTaskResponse)
        assert result.id == "task-1"
        assert result.status.state == "TASK_STATE_COMPLETED"


class TestEventTriggersRuns:
    async def test_returns_paginated_runs(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {"items": [_RUN_RESULT], "next_cursor": "2026-06-28T12:00:25Z"}
        )

        result = await client.event_triggers.runs(_TRIGGER["id"], limit=5, cursor="page-2")

        _, kwargs = mock_http.get.call_args
        assert kwargs["params"] == {"limit": 5, "cursor": "page-2"}
        assert isinstance(result, EventRunResultsResponse)
        assert isinstance(result.items[0], EventRunResultItem)
        assert isinstance(result, ScheduledRunsPage)
        assert isinstance(result.items[0], ScheduledRunResult)
        assert result.next_cursor == "2026-06-28T12:00:25Z"
        assert result.items[0].chain_id == "event-chain-1"
        assert result.items[0].hop_index == 2

    async def test_parses_bare_array_with_omitted_and_nullable_fields(self, client, mock_http):
        optional_fields = {"output_text", "error", "chain_id", "hop_index"}
        required_run = {
            key: value for key, value in _RUN_RESULT.items() if key not in optional_fields
        }
        nullable_run = {
            **required_run,
            "id": "result-nullable",
            **{field: None for field in optional_fields},
        }
        mock_http.get.return_value = _json_response([required_run, nullable_run])

        result = await client.event_triggers.runs(_TRIGGER["id"])

        assert isinstance(result, EventRunResultsResponse)
        assert result.next_cursor is None
        assert result.items[0].output_text == ""
        assert result.items[0].error == ""
        assert result.items[0].chain_id is None
        assert result.items[0].hop_index is None
        assert result.items[1].output_text is None
        assert result.items[1].error is None
        assert result.items[1].chain_id is None
        assert result.items[1].hop_index is None

    @pytest.mark.parametrize(
        "body", [{}, {"next_cursor": "page-2"}, {"items": {}}, {"items": None}, {"items": [{}]}]
    )
    async def test_rejects_malformed_response(self, client, mock_http, body):
        mock_http.get.return_value = _json_response(body)

        with pytest.raises(ValidationError):
            await client.event_triggers.runs(_TRIGGER["id"])

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
        assert all(isinstance(item, EventRunResultItem) for item in items)
        first_call = mock_http.get.call_args_list[0]
        second_call = mock_http.get.call_args_list[1]
        assert first_call.kwargs["params"] == {"limit": 1}
        assert second_call.kwargs["params"] == {"limit": 1, "cursor": "page-2"}
