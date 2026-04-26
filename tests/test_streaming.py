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
    format_usdc,
    iter_sse_events,
    parse_marketplace_tool_name,
    parse_usdc,
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
    async def test_wire_format_event_field(self):
        """Standard SSE wire format: separate `event:` line (not embedded in JSON)."""
        lines = [
            "event: CUSTOM_TYPE",
            'data: {"key": "value"}',
            "",
        ]
        events = [e async for e in iter_sse_events(_FakeResponse(lines))]
        assert len(events) == 1
        # event: field becomes sse_event_type fallback; JSON has no "event" key
        assert events[0].type == "CUSTOM_TYPE"
        assert events[0].data == {"key": "value"}

    @pytest.mark.asyncio
    async def test_json_dict_without_event_key(self):
        """JSON data that is a dict but lacks 'event' key hits the else branch."""
        lines = [
            'data: {"foo": "bar"}',
            "",
        ]
        events = [e async for e in iter_sse_events(_FakeResponse(lines))]
        assert len(events) == 1
        assert events[0].data == {"foo": "bar"}
        assert events[0].type == "message"

    @pytest.mark.asyncio
    async def test_malformed_json_starting_with_brace(self):
        """Data starting with '{' but invalid JSON hits the JSONDecodeError except branch."""
        lines = [
            "data: {not valid json}",
            "",
        ]
        events = [e async for e in iter_sse_events(_FakeResponse(lines))]
        assert len(events) == 1
        assert events[0].data == {"raw": "{not valid json}"}

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


# ─── parse_marketplace_tool_name ─────────────────────────────────────────────


class TestParseMarketplaceToolName:
    def test_standard_format(self):
        result = parse_marketplace_tool_name("acme/search")
        assert result == {"org_slug": "acme", "tool_name": "search"}

    def test_platform_slug(self):
        result = parse_marketplace_tool_name("platform/geocode")
        assert result == {"org_slug": "platform", "tool_name": "geocode"}

    def test_nested_slash_splits_on_first(self):
        result = parse_marketplace_tool_name("acme/foo/bar")
        assert result == {"org_slug": "acme", "tool_name": "foo/bar"}

    def test_no_slash_raises_value_error(self):
        with pytest.raises(ValueError, match="org_slug/tool_name"):
            parse_marketplace_tool_name("noseparator")

    def test_leading_slash_raises_value_error(self):
        # idx == 0 → org_slug would be empty string
        with pytest.raises(ValueError):
            parse_marketplace_tool_name("/tool_name")


# ─── format_usdc ──────────────────────────────────────────────────────────────


class TestFormatUsdc:
    def test_one_and_a_half(self):
        assert format_usdc(1_500_000) == "1.500000"

    def test_small_value(self):
        assert format_usdc(50) == "0.000050"

    def test_zero(self):
        assert format_usdc(0) == "0.000000"

    def test_one_dollar(self):
        assert format_usdc(1_000_000) == "1.000000"


# ─── parse_usdc ───────────────────────────────────────────────────────────────


class TestParseUsdc:
    def test_one_fifty(self):
        assert parse_usdc("1.50") == 1_500_000

    def test_quarter_dollar(self):
        assert parse_usdc("0.25") == 250_000

    def test_float_input(self):
        assert parse_usdc(0.5) == 500_000

    def test_zero(self):
        assert parse_usdc("0") == 0

    def test_round_trip(self):
        original = 123_456
        assert parse_usdc(format_usdc(original)) == original
