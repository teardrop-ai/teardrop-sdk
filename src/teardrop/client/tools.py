"""Organization tool-management client methods."""

from __future__ import annotations

from typing import Any

from teardrop.models import (
    CreateOrgToolRequest,
    OrgToolResponse,
    TestWebhookRequest,
    TestWebhookResponse,
    ToolDeletedResponse,
    UpdateOrgToolRequest,
)


class _ToolsMixin:
    async def create_tool(self, request: CreateOrgToolRequest) -> OrgToolResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/tools",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return OrgToolResponse.model_validate(resp.json())

    async def list_tools(self) -> list[OrgToolResponse]:
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/tools", headers=await self._headers())
        self._raise_for_status(resp)
        data = resp.json()
        if isinstance(data, list):
            return [OrgToolResponse.model_validate(item) for item in data]
        return [OrgToolResponse.model_validate(item) for item in data.get("items", [])]

    async def get_tool(self, tool_id: str) -> OrgToolResponse:
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/tools/{tool_id}", headers=await self._headers())
        self._raise_for_status(resp)
        return OrgToolResponse.model_validate(resp.json())

    async def update_tool(self, tool_id: str, request: UpdateOrgToolRequest) -> OrgToolResponse:
        http = await self._get_http()
        resp = await http.patch(
            f"{self._base_url}/tools/{tool_id}",
            json=request.model_dump(exclude_unset=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return OrgToolResponse.model_validate(resp.json())

    async def delete_tool(self, tool_id: str) -> ToolDeletedResponse:
        http = await self._get_http()
        resp = await http.delete(f"{self._base_url}/tools/{tool_id}", headers=await self._headers())
        self._raise_for_status(resp)
        return ToolDeletedResponse.model_validate(resp.json())

    async def test_webhook(
        self, request_or_tool_id: TestWebhookRequest | str, payload: dict[str, Any] | None = None
    ) -> TestWebhookResponse:
        http = await self._get_http()
        if isinstance(request_or_tool_id, TestWebhookRequest):
            body: dict[str, Any] = request_or_tool_id.model_dump(exclude_none=True)
        else:
            body = {"tool_id": request_or_tool_id, "payload": payload or {}}
        resp = await http.post(
            f"{self._base_url}/tools/test-webhook",
            json=body,
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return TestWebhookResponse.model_validate(resp.json())
