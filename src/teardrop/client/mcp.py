"""MCP server-management client methods."""

from __future__ import annotations

from typing import Any

from teardrop.models import (
    CreateMcpServerRequest,
    DiscoverMcpToolsResponse,
    McpServerDeletedResponse,
    McpServerResponse,
    TestMcpToolResponse,
    UpdateMcpServerRequest,
)


class _McpMixin:
    async def create_mcp_server(self, request: CreateMcpServerRequest) -> McpServerResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/mcp/servers",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return McpServerResponse.model_validate(resp.json())

    async def list_mcp_servers(self) -> list[McpServerResponse]:
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/mcp/servers", headers=await self._headers())
        self._raise_for_status(resp)
        data = resp.json()
        if isinstance(data, list):
            return [McpServerResponse.model_validate(item) for item in data]
        return [McpServerResponse.model_validate(item) for item in data.get("items", [])]

    async def get_mcp_server(self, server_id: str) -> McpServerResponse:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/mcp/servers/{server_id}", headers=await self._headers()
        )
        self._raise_for_status(resp)
        return McpServerResponse.model_validate(resp.json())

    async def update_mcp_server(
        self, server_id: str, request: UpdateMcpServerRequest
    ) -> McpServerResponse:
        http = await self._get_http()
        resp = await http.patch(
            f"{self._base_url}/mcp/servers/{server_id}",
            json=request.model_dump(exclude_unset=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return McpServerResponse.model_validate(resp.json())

    async def delete_mcp_server(self, server_id: str) -> McpServerDeletedResponse:
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/mcp/servers/{server_id}", headers=await self._headers()
        )
        self._raise_for_status(resp)
        return McpServerDeletedResponse.model_validate(resp.json())

    async def discover_mcp_server_tools(self, server_id: str) -> DiscoverMcpToolsResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/mcp/servers/{server_id}/discover",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return DiscoverMcpToolsResponse.model_validate(resp.json())

    async def test_mcp_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> TestMcpToolResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/mcp/servers/{server_id}/test-tool",
            json={"tool_name": tool_name, "arguments": arguments},
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return TestMcpToolResponse.model_validate(resp.json())
