"""Integration write+undo smoke tests.

Each test creates a resource, asserts the response shape, then deletes it in
a ``finally`` block to guarantee cleanup even when assertions fail.

Skipped automatically when integration env vars are not set.
"""

from __future__ import annotations

import pytest

from teardrop.client import AsyncTeardropClient
from teardrop.models import (
    CreateMcpServerRequest,
    CreateOrgToolRequest,
    MemoryEntry,
    OrgMcpServer,
    OrgTool,
    StoreMemoryRequest,
)


class TestMemoryRoundTrip:
    async def test_create_and_delete_memory(self, async_client: AsyncTeardropClient) -> None:
        memory: MemoryEntry | None = None
        try:
            memory = await async_client.create_memory(
                StoreMemoryRequest(content="__smoke_test__ ok")
            )
            assert memory.id
            assert "__smoke_test__" in memory.content
        finally:
            if memory is not None:
                await async_client.delete_memory(memory.id)


class TestToolRoundTrip:
    async def test_create_and_delete_tool(self, async_client: AsyncTeardropClient) -> None:
        tool: OrgTool | None = None
        try:
            tool = await async_client.create_tool(
                CreateOrgToolRequest(
                    name="smoketool",
                    description="Smoke test tool — safe to delete",
                    input_schema={"type": "object", "properties": {}, "required": []},
                    webhook_url="https://example.com/smoke-tool",
                )
            )
            assert tool.id
            assert tool.name == "smoketool"
        finally:
            if tool is not None:
                await async_client.delete_tool(tool.id)


class TestMcpServerRoundTrip:
    async def test_create_and_delete_mcp_server(
        self, async_client: AsyncTeardropClient
    ) -> None:
        server: OrgMcpServer | None = None
        try:
            server = await async_client.create_mcp_server(
                CreateMcpServerRequest(
                    name="smokemcp",
                    url="https://example.com/smoke-mcp",
                )
            )
            assert server.id
            assert server.name == "smokemcp"
        finally:
            if server is not None:
                await async_client.delete_mcp_server(server.id)
