"""MCP server-management client methods."""

from __future__ import annotations

from teardrop.client._core import _parse_list_response
from teardrop.models import (
    CreateMcpServerRequest,
    DiscoverMcpToolsResponse,
    OrgMcpServer,
    UpdateMcpServerRequest,
)


class _McpMixin:
    async def create_mcp_server(self, request: CreateMcpServerRequest) -> OrgMcpServer:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/mcp/servers",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return OrgMcpServer.model_validate(resp.json())

    async def list_mcp_servers(self) -> list[OrgMcpServer]:
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/mcp/servers", headers=await self._headers())
        self._raise_for_status(resp)
        return _parse_list_response(resp.json(), OrgMcpServer, item_container="items")

    async def get_mcp_server(self, server_id: str) -> OrgMcpServer:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/mcp/servers/{server_id}", headers=await self._headers()
        )
        self._raise_for_status(resp)
        return OrgMcpServer.model_validate(resp.json())

    async def update_mcp_server(
        self, server_id: str, request: UpdateMcpServerRequest
    ) -> OrgMcpServer:
        http = await self._get_http()
        resp = await http.patch(
            f"{self._base_url}/mcp/servers/{server_id}",
            json=request.model_dump(exclude_unset=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return OrgMcpServer.model_validate(resp.json())

    async def delete_mcp_server(self, server_id: str) -> None:
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/mcp/servers/{server_id}", headers=await self._headers()
        )
        self._raise_for_status(resp)

    async def discover_mcp_server_tools(self, server_id: str) -> DiscoverMcpToolsResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/mcp/servers/{server_id}/discover",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return DiscoverMcpToolsResponse.model_validate(resp.json())
