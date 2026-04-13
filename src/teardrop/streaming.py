"""SSE stream parser for Teardrop /agent/run responses."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Literal, TypedDict

import httpx

from teardrop.models import SSEEvent

# Event types emitted by the Teardrop server.
EVENT_RUN_STARTED = "RUN_STARTED"
EVENT_RUN_FINISHED = "RUN_FINISHED"
EVENT_TEXT_MSG_CONTENT = "TEXT_MESSAGE_CONTENT"
EVENT_TOOL_CALL_START = "TOOL_CALL_START"
EVENT_TOOL_CALL_END = "TOOL_CALL_END"
EVENT_SURFACE_UPDATE = "SURFACE_UPDATE"
EVENT_USAGE_SUMMARY = "USAGE_SUMMARY"
EVENT_BILLING_SETTLEMENT = "BILLING_SETTLEMENT"
EVENT_ERROR = "ERROR"
EVENT_DONE = "DONE"


def _build_event(
    sse_event_type: str,
    event_id: str,
    retry_ms: int | None,
    data_buf: list[str],
) -> SSEEvent:
    """Construct an SSEEvent from a completed SSE block.

    The backend sends events in the format::

        data: {"event": "<type>", "data": { ... }}\n\n

    The ``event:`` SSE framing field is NOT used by the backend; the event
    type is embedded inside the JSON payload.  The ``sse_event_type`` parameter
    is kept as a fallback for streams that do use the SSE framing field.

    Uses ``model_construct`` to bypass Pydantic field validation — safe because
    all values originate from the SDK's own parser, not user input.
    """
    data: dict[str, Any] = {}
    event_type: str = sse_event_type

    if data_buf:
        data_str = "\n".join(data_buf)
        if data_str and data_str[0] in ("{", "["):
            try:
                parsed = json.loads(data_str)
                if isinstance(parsed, dict) and "event" in parsed:
                    # Spec format: {"event": "TYPE", "data": {...}}
                    event_type = parsed.get("event", sse_event_type)
                    inner = parsed.get("data", {})
                    data = inner if isinstance(inner, dict) else {"value": inner}
                else:
                    data = parsed if isinstance(parsed, dict) else {"value": parsed}
            except json.JSONDecodeError:
                data = {"raw": data_str}
        elif data_str:
            data = {"raw": data_str}
    return SSEEvent.model_construct(
        type=event_type or "message",
        data=data,
        id=event_id,
        retry=retry_ms,
    )


async def iter_sse_events(response: httpx.Response) -> AsyncIterator[SSEEvent]:
    """Parse an SSE byte stream into typed ``SSEEvent`` objects.

    Handles both the spec-mandated format (event type embedded in JSON)::

        data: {"event": "TYPE", "data": {...}}\n\n

    and the standard SSE wire format (for compatibility)::

        event: EVENT_TYPE\n
        data: {"key": "value"}\n
        \n

    Yields one ``SSEEvent`` per complete event block.  Ignores ``:`` comment
    lines (SSE heartbeats).
    """
    event_type: str = ""
    event_id: str = ""
    retry_ms: int | None = None
    data_buf: list[str] = []

    async for raw_line in response.aiter_lines():
        # Single-pass strip handles both \r\n and bare \n / \r line endings.
        line = raw_line.rstrip("\r\n")

        if line.startswith(":"):
            # SSE comment / heartbeat — ignore per spec.
            continue
        elif line.startswith("event:"):
            event_type = line[6:].lstrip(" ")
        elif line.startswith("id:"):
            event_id = line[3:].lstrip(" ")
        elif line.startswith("retry:"):
            raw_retry = line[6:].lstrip(" ")
            try:
                retry_ms = int(raw_retry)
            except ValueError:
                pass
        elif line.startswith("data:"):
            data_buf.append(line[5:].lstrip(" "))
        elif line == "":
            # Empty line = end of event block.
            if event_type or data_buf:
                yield _build_event(event_type, event_id, retry_ms, data_buf)
                event_type = ""
                event_id = ""
                retry_ms = None
                data_buf = []

    # Flush any trailing event without a final blank line.
    if event_type or data_buf:
        yield _build_event(event_type, event_id, retry_ms, data_buf)


def collect_text(events: list[SSEEvent]) -> str:
    """Convenience: concatenate all TEXT_MESSAGE_CONTENT deltas into a string."""
    return "".join(
        e.data.get("delta", "") for e in events if e.type == EVENT_TEXT_MSG_CONTENT
    )


async def async_collect_text(events: AsyncIterator[SSEEvent]) -> str:
    """Async version of ``collect_text``: drain an async SSE event stream and
    return the concatenated TEXT_MESSAGE_CONTENT deltas as a string.
    """
    parts: list[str] = []
    async for event in events:
        if event.type == EVENT_TEXT_MSG_CONTENT:
            parts.append(event.data.get("delta", ""))
    return "".join(parts)


# ─── MCP tool name utilities ──────────────────────────────────────────────────

_MCP_SEPARATOR = "__"


class _McpToolMatch(TypedDict):
    is_mcp: Literal[True]
    server: str
    tool: str


class _McpToolNoMatch(TypedDict):
    is_mcp: Literal[False]


def parse_mcp_tool_name(tool_name: str) -> _McpToolMatch | _McpToolNoMatch:
    """Split an MCP-namespaced tool name into server and tool components.

    MCP server tools use a double-underscore separator::

        "{server_name}__{mcp_tool_name}"

    A single underscore is NOT a separator — it may appear in both the server
    name and the tool name.

    Returns a dict with ``is_mcp=True, server=..., tool=...`` when the
    separator is found at a non-zero position, or ``{"is_mcp": False}`` for
    global / org webhook tools.

    Examples::

        parse_mcp_tool_name("my_server__web_search")
        # → {"is_mcp": True, "server": "my_server", "tool": "web_search"}

        parse_mcp_tool_name("web_search")
        # → {"is_mcp": False}
    """
    idx = tool_name.find(_MCP_SEPARATOR)
    if idx > 0:
        return {
            "is_mcp": True,
            "server": tool_name[:idx],
            "tool": tool_name[idx + len(_MCP_SEPARATOR) :],
        }
    return {"is_mcp": False}

