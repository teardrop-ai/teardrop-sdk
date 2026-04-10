"""SSE stream parser for Teardrop /agent/run responses."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from teardrop.models import SSEEvent

# Event types emitted by the Teardrop server.
EVENT_RUN_STARTED = "RUN_STARTED"
EVENT_RUN_FINISHED = "RUN_FINISHED"
EVENT_TEXT_MSG_START = "TEXT_MESSAGE_START"
EVENT_TEXT_MSG_CONTENT = "TEXT_MESSAGE_CONTENT"
EVENT_TEXT_MSG_END = "TEXT_MESSAGE_END"
EVENT_TOOL_CALL_START = "TOOL_CALL_START"
EVENT_TOOL_CALL_END = "TOOL_CALL_END"
EVENT_STATE_SNAPSHOT = "STATE_SNAPSHOT"
EVENT_SURFACE_UPDATE = "SURFACE_UPDATE"
EVENT_USAGE_SUMMARY = "USAGE_SUMMARY"
EVENT_BILLING_SETTLEMENT = "BILLING_SETTLEMENT"
EVENT_ERROR = "ERROR"
EVENT_DONE = "DONE"


async def iter_sse_events(response: httpx.Response) -> AsyncIterator[SSEEvent]:
    """Parse an SSE byte stream into typed ``SSEEvent`` objects.

    Handles the standard SSE wire format::

        event: EVENT_TYPE\\n
        data: {"key": "value"}\\n
        \\n

    Yields one ``SSEEvent`` per complete event block.
    """
    event_type: str = ""
    data_buf: list[str] = []

    async for raw_line in response.aiter_lines():
        line = raw_line.rstrip("\n").rstrip("\r")

        if line.startswith("event:"):
            event_type = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_buf.append(line[len("data:"):].strip())
        elif line == "":
            # Empty line = end of event block.
            if event_type or data_buf:
                data_str = "\n".join(data_buf)
                data: dict[str, Any] = {}
                if data_str:
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        data = {"raw": data_str}
                yield SSEEvent(type=event_type or "message", data=data)
                event_type = ""
                data_buf = []

    # Flush any trailing event without a final blank line.
    if event_type or data_buf:
        data_str = "\n".join(data_buf)
        data = {}
        if data_str:
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                data = {"raw": data_str}
        yield SSEEvent(type=event_type or "message", data=data)


def collect_text(events: list[SSEEvent]) -> str:
    """Convenience: concatenate all TEXT_MESSAGE_CONTENT deltas into a string."""
    return "".join(
        e.data.get("delta", "") for e in events if e.type == EVENT_TEXT_MSG_CONTENT
    )
