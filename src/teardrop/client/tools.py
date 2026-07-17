"""Organization tool-management client methods."""

from __future__ import annotations

from teardrop.client._core import _parse_list_response
from teardrop.models import (
    CreateOrgToolRequest,
    OrgTool,
    TestWebhookRequest,
    TestWebhookResponse,
    UpdateOrgToolRequest,
)


class _ToolsMixin:
    async def create_tool(self, request: CreateOrgToolRequest) -> OrgTool:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/tools",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return OrgTool.model_validate(resp.json())

    async def list_tools(self) -> list[OrgTool]:
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/tools", headers=await self._headers())
        self._raise_for_status(resp)
        return _parse_list_response(resp.json(), OrgTool, item_container="items")

    async def get_tool(self, tool_id: str) -> OrgTool:
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/tools/{tool_id}", headers=await self._headers())
        self._raise_for_status(resp)
        return OrgTool.model_validate(resp.json())

    async def update_tool(self, tool_id: str, request: UpdateOrgToolRequest) -> OrgTool:
        http = await self._get_http()
        resp = await http.patch(
            f"{self._base_url}/tools/{tool_id}",
            json=request.model_dump(exclude_unset=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return OrgTool.model_validate(resp.json())

    async def delete_tool(self, tool_id: str) -> None:
        http = await self._get_http()
        resp = await http.delete(f"{self._base_url}/tools/{tool_id}", headers=await self._headers())
        self._raise_for_status(resp)

    async def test_webhook(self, request: TestWebhookRequest) -> TestWebhookResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/tools/test-webhook",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return TestWebhookResponse.model_validate(resp.json())
