"""Tests for teardrop.streaming — SSE parser."""

from __future__ import annotations

import pytest

from teardrop.models import SSEEvent
from teardrop.streaming import (
    EVENT_DONE,
    EVENT_RUN_STARTED,
    EVENT_TEXT_MSG_CONTENT,
    async_collect_text,
    collect_text,
    iter_sse_events,
)

# Helper: build a spec-format SSE data line
def _sse(event: str, data: dict | None = None) -> str:
    import json
    payload = {"event": event, "data": data or {}}
    return f'data: {json.dumps(payload)}'


class _FakeResponse:
    """Mimics httpx.Response.aiter_lines() for testing."""

    def __init__(self, lines: list[str]):
        self._lines = lines

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class TestIterSseEvents:
    @pytest.mark.asyncio
    async def test_single_event(self):
        lines = [
            _sse("RUN_STARTED", {"thread_id": "abc"}),
            "",
        ]
        events = [e async for e in iter_sse_events(_FakeResponse(lines))]
        assert len(events) == 1
        assert events[0].type == EVENT_RUN_STARTED
        assert events[0].data["thread_id"] == "abc"

    @pytest.mark.asyncio
    async def test_multiple_events(self):
        lines = [
            _sse("RUN_STARTED", {"id": "1"}),
            "",
            _sse("TEXT_MESSAGE_CONTENT", {"delta": "Hello"}),
            "",
            _sse("DONE"),
            "",
        ]
        events = [e async for e in iter_sse_events(_FakeResponse(lines))]
        assert len(events) == 3
        assert events[0].type == EVENT_RUN_STARTED
        assert events[1].type == EVENT_TEXT_MSG_CONTENT
        assert events[2].type == EVENT_DONE

    @pytest.mark.asyncio
    async def test_non_json_data_falls_back_to_raw(self):
        lines = [
            "data: not-json-at-all",
            "",
        ]
        events = [e async for e in iter_sse_events(_FakeResponse(lines))]
        assert len(events) == 1
        assert events[0].data == {"raw": "not-json-at-all"}

    @pytest.mark.asyncio
    async def test_trailing_event_without_blank_line(self):
        """An event at EOF without a final blank line should still be yielded."""
        lines = [
            _sse("DONE"),
        ]
        events = [e async for e in iter_sse_events(_FakeResponse(lines))]
        assert len(events) == 1
        assert events[0].type == EVENT_DONE

    @pytest.mark.asyncio
    async def test_empty_data_yields_empty_dict(self):
        lines = [
            _sse("RUN_STARTED"),
            "",
        ]
        events = [e async for e in iter_sse_events(_FakeResponse(lines))]
        assert len(events) == 1
        assert events[0].data == {}

    @pytest.mark.asyncio
    async def test_multiline_data(self):
        """Multiple data: lines should be joined with newlines before parsing."""
        # Each continuation must also start with "data:" per SSE spec
        lines = [
            'data: {"event": "SURFACE_UPDATE",',
            'data:  "data": {"key": "value"}}',
            "",
        ]
        events = [e async for e in iter_sse_events(_FakeResponse(lines))]
        assert len(events) == 1
        assert events[0].type == "SURFACE_UPDATE"
        assert events[0].data == {"key": "value"}

    @pytest.mark.asyncio
    async def test_id_field_parsed(self):
        lines = [
            "id: evt-42",
            _sse("TEXT_MESSAGE_CONTENT", {"delta": "hi"}),
            "",
        ]
        events = [e async for e in iter_sse_events(_FakeResponse(lines))]
        assert len(events) == 1
        assert events[0].id == "evt-42"

    @pytest.mark.asyncio
    async def test_comment_lines_are_ignored(self):
        """Lines starting with ':' are SSE heartbeats/comments and must be ignored."""
        lines = [
            ": heartbeat",
            _sse("RUN_STARTED"),
            "",
        ]
        events = [e async for e in iter_sse_events(_FakeResponse(lines))]
        assert len(events) == 1
        assert events[0].type == EVENT_RUN_STARTED

    @pytest.mark.asyncio
    async def test_retry_field_parsed(self):
        lines = [
            "retry: 3000",
            _sse("RUN_STARTED"),
            "",
        ]
        events = [e async for e in iter_sse_events(_FakeResponse(lines))]
        assert len(events) == 1
        assert events[0].retry == 3000

    @pytest.mark.asyncio
    async def test_retry_invalid_value_ignored(self):
        lines = [
            "retry: not-a-number",
            _sse("RUN_STARTED"),
            "",
        ]
        events = [e async for e in iter_sse_events(_FakeResponse(lines))]
        assert len(events) == 1
        assert events[0].retry is None

    @pytest.mark.asyncio
    async def test_id_resets_between_events(self):
        """id: field should reset between event blocks."""
        lines = [
            "id: evt-1",
            _sse("RUN_STARTED"),
            "",
            _sse("DONE"),
            "",
        ]
        events = [e async for e in iter_sse_events(_FakeResponse(lines))]
        assert events[0].id == "evt-1"
        assert events[1].id == ""


class TestCollectText:
    def test_concatenates_deltas(self):
        events = [
            SSEEvent(type=EVENT_TEXT_MSG_CONTENT, data={"delta": "Hello"}),
            SSEEvent(type=EVENT_TEXT_MSG_CONTENT, data={"delta": " world"}),
            SSEEvent(type=EVENT_DONE, data={}),
        ]
        assert collect_text(events) == "Hello world"

    def test_empty_events(self):
        assert collect_text([]) == ""

    def test_ignores_non_content_events(self):
        events = [
            SSEEvent(type=EVENT_RUN_STARTED, data={}),
            SSEEvent(type=EVENT_TEXT_MSG_CONTENT, data={"delta": "hi"}),
            SSEEvent(type=EVENT_DONE, data={}),
        ]
        assert collect_text(events) == "hi"


class TestAsyncCollectText:
    @pytest.mark.asyncio
    async def test_concatenates_deltas(self):
        async def _source():
            yield SSEEvent(type=EVENT_RUN_STARTED, data={})
            yield SSEEvent(type=EVENT_TEXT_MSG_CONTENT, data={"delta": "Hello"})
            yield SSEEvent(type=EVENT_TEXT_MSG_CONTENT, data={"delta": " world"})
            yield SSEEvent(type=EVENT_DONE, data={})

        result = await async_collect_text(_source())
        assert result == "Hello world"

    @pytest.mark.asyncio
    async def test_empty_stream(self):
        async def _source():
            return
            yield  # make it an async generator

        result = await async_collect_text(_source())
        assert result == ""

    @pytest.mark.asyncio
    async def test_ignores_non_content_events(self):
        async def _source():
            yield SSEEvent(type=EVENT_RUN_STARTED, data={})
            yield SSEEvent(type=EVENT_TEXT_MSG_CONTENT, data={"delta": "hi"})

        result = await async_collect_text(_source())
        assert result == "hi"
