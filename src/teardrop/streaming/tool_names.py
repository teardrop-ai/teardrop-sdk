"""Helpers for parsing namespaced tool identifiers."""

from __future__ import annotations

from typing import Literal, TypedDict

_MCP_SEPARATOR = "__"
_MARKETPLACE_SEPARATOR = "/"


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

    A single underscore is NOT a separator - it may appear in both the server
    name and the tool name.

    Returns a dict with ``is_mcp=True, server=..., tool=...`` when the
    separator is found at a non-zero position, or ``{"is_mcp": False}`` for
    global / org webhook tools.
    """
    idx = tool_name.find(_MCP_SEPARATOR)
    if idx > 0:
        return {
            "is_mcp": True,
            "server": tool_name[:idx],
            "tool": tool_name[idx + len(_MCP_SEPARATOR) :],
        }
    return {"is_mcp": False}


def parse_marketplace_tool_name(qualified_name: str) -> dict[str, str]:
    """Parse a qualified marketplace tool name into its components.

    Marketplace tools use ``org_slug/tool_name`` format.

    Returns a dict with ``org_slug`` and ``tool_name``.
    """
    idx = qualified_name.find(_MARKETPLACE_SEPARATOR)
    if idx <= 0:
        raise ValueError(
            f"Invalid qualified tool name {qualified_name!r}: expected 'org_slug/tool_name' format"
        )
    return {
        "org_slug": qualified_name[:idx],
        "tool_name": qualified_name[idx + 1 :],
    }
