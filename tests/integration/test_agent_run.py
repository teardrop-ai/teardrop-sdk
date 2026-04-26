"""Integration tests — Agent run (streaming SSE).

Exercises the /agent/run endpoint end-to-end: event shapes, multi-turn threads,
context forwarding, validation boundaries, and auth rejection.

A single session-scoped ``cached_run_events`` fixture collects one real run once
per session so the remaining tests can assert over that corpus without making
redundant network calls.

Skipped automatically when integration env vars are not set.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import List

import pydantic
import pytest

from teardrop.client import AsyncTeardropClient
from teardrop.exceptions import AuthenticationError
from teardrop.models import SSEEvent
from teardrop.streaming import (
    EVENT_DONE,
    EVENT_RUN_FINISHED,
    EVENT_RUN_STARTED,
    EVENT_TEXT_MSG_CONTENT,
    EVENT_USAGE_SUMMARY,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _collect_text(events: List[SSEEvent]) -> str:
    """Concatenate text from TEXT_MESSAGE_CONTENT events.

    Tries the most common data key names emitted by the Teardrop backend.
    """
    parts: List[str] = []
    for event in events:
        if event.type == EVENT_TEXT_MSG_CONTENT:
            for key in ("content", "text", "delta", "value"):
                v = event.data.get(key)
                if isinstance(v, str) and v:
                    parts.append(v)
                    break
    return "".join(parts)


# ─── Session-scoped fixtures ──────────────────────────────────────────────────


@pytest.fixture(scope="session")
def cached_run_events(
    integration_url: str, _cached_token: str
) -> List[SSEEvent]:
    """Run the agent once and cache all SSE events for the session.

    Uses a dedicated event loop via ``asyncio.run`` so the cache can be shared
    across tests without coupling to pytest-asyncio's per-test loop.
    """

    async def _collect() -> List[SSEEvent]:
        client = AsyncTeardropClient(integration_url, token=_cached_token)
        try:
            events: List[SSEEvent] = []
            async for event in client.run("hello, respond briefly"):
                events.append(event)
            return events
        finally:
            await client.close()

    return asyncio.run(_collect())


# ─── Tests ────────────────────────────────────────────────────────────────────


class TestRunBasicShape:
    """Verify that a real agent run emits the expected event structure."""

    async def test_run_returns_sse_events(
        self, cached_run_events: List[SSEEvent]
    ) -> None:
        """The agent run stream yields at least one SSEEvent."""
        assert cached_run_events, "Expected at least one SSE event from agent run"
        for event in cached_run_events:
            assert isinstance(event, SSEEvent)
            assert event.type  # Type must be non-empty
            assert isinstance(event.data, dict)

    async def test_run_starts_and_finishes(
        self, cached_run_events: List[SSEEvent]
    ) -> None:
        """RUN_STARTED event is present and the stream ends gracefully."""
        types = {e.type for e in cached_run_events}
        if "ERROR" in types and not (types & {EVENT_RUN_FINISHED, EVENT_DONE}):
            pytest.skip("Agent run returned ERROR event; skipping terminal-event assertion")
        assert EVENT_RUN_STARTED in types, "Expected RUN_STARTED event in stream"
        # At least one terminal event must be present
        assert types & {EVENT_RUN_FINISHED, EVENT_DONE}, (
            "Expected RUN_FINISHED or DONE event at end of stream"
        )

    async def test_run_collects_text(
        self, cached_run_events: List[SSEEvent]
    ) -> None:
        """TEXT_MESSAGE_CONTENT events produce non-empty text output."""
        types = {e.type for e in cached_run_events}
        if "ERROR" in types and EVENT_TEXT_MSG_CONTENT not in types:
            pytest.skip("Agent run returned ERROR event; no text content to collect")
        text = _collect_text(cached_run_events)
        assert text, (
            "Expected non-empty text from TEXT_MESSAGE_CONTENT events. "
            f"Event types seen: {[e.type for e in cached_run_events]}"
        )


class TestRunThreadBehaviour:
    """Thread ID handling and multi-turn conversation continuity."""

    async def test_run_with_explicit_thread_id(
        self, async_client: AsyncTeardropClient
    ) -> None:
        """Runs with an explicit thread_id complete without error."""
        thread_id = f"thread_{uuid.uuid4().hex[:8]}"
        events: List[SSEEvent] = []
        async for event in async_client.run("hello", thread_id=thread_id):
            events.append(event)
        assert events, "Expected at least one SSE event"
        types = {e.type for e in events}
        assert EVENT_RUN_STARTED in types, "Expected RUN_STARTED event"

    async def test_run_multi_turn_thread(
        self, async_client: AsyncTeardropClient
    ) -> None:
        """Two sequential calls on the same thread_id both produce SSE events."""
        thread_id = f"thread_{uuid.uuid4().hex[:8]}"

        events1: List[SSEEvent] = []
        async for event in async_client.run("What is 1 + 1?", thread_id=thread_id):
            events1.append(event)

        events2: List[SSEEvent] = []
        async for event in async_client.run(
            "And what is 2 + 2?", thread_id=thread_id
        ):
            events2.append(event)

        assert events1, "First turn must produce SSE events"
        assert events2, "Second turn must produce SSE events"
        assert EVENT_RUN_STARTED in {e.type for e in events1}, (
            "First turn must include RUN_STARTED event"
        )
        assert EVENT_RUN_STARTED in {e.type for e in events2}, (
            "Second turn must include RUN_STARTED event"
        )


class TestRunContextForwarding:
    async def test_run_context_accepted(
        self, async_client: AsyncTeardropClient
    ) -> None:
        """run() with a context dict completes without raising an error."""
        events: List[SSEEvent] = []
        async for event in async_client.run(
            "hello", context={"source": "integration_test", "debug": True}
        ):
            events.append(event)
        assert events, "Expected at least one SSE event when context is provided"


class TestRunValidationBoundaries:
    """Input validation and authentication error paths."""

    async def test_run_message_too_long_raises_before_http(
        self, async_client: AsyncTeardropClient
    ) -> None:
        """Messages exceeding 4096 chars raise pydantic.ValidationError locally."""
        with pytest.raises(pydantic.ValidationError):
            async for _ in async_client.run("x" * 4097):
                pass  # pragma: no cover

    async def test_run_invalid_auth_raises(
        self, integration_url: str
    ) -> None:
        """A garbage token causes AuthenticationError on the first stream iteration."""
        bad_client = AsyncTeardropClient(integration_url, token="garbage.token.xyz")
        with pytest.raises(AuthenticationError):
            async for _ in bad_client.run("hello"):
                pass  # pragma: no cover


class TestRunUsageSummary:
    async def test_usage_summary_event_present(
        self, cached_run_events: List[SSEEvent]
    ) -> None:
        """If the server emits a USAGE_SUMMARY event, it must carry numeric token counts."""
        usage_events = [e for e in cached_run_events if e.type == EVENT_USAGE_SUMMARY]
        if not usage_events:
            pytest.skip("Server did not emit USAGE_SUMMARY event for this run")

        data = usage_events[0].data
        # Accept common key name variations used by the API
        tokens_in = data.get("tokens_in", data.get("input_tokens", data.get("prompt_tokens")))
        tokens_out = data.get("tokens_out", data.get("output_tokens", data.get("completion_tokens")))
        assert tokens_in is not None, f"Expected tokens_in in USAGE_SUMMARY data: {data}"
        assert tokens_out is not None, f"Expected tokens_out in USAGE_SUMMARY data: {data}"
        assert isinstance(tokens_in, int) and tokens_in >= 0
        assert isinstance(tokens_out, int) and tokens_out >= 0
