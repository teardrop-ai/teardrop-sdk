"""Agent-run client methods."""

from __future__ import annotations

import uuid
from typing import Any, AsyncIterator

from teardrop.models import (
    AgentDecisionListResponse,
    AgentDecisionsResponse,
    AgentRunRequest,
    AgentTool,
    AgentToolsResponse,
    EventDispatchResponse,
    RunOutcomeRequest,
    RunOutcomeResponse,
    SSEEvent,
    ToolExclusionActionResponse,
    ToolExclusionCreateResponse,
    ToolExclusionListResponse,
    ToolExclusionRemovedResponse,
    ToolExclusionRequest,
    ToolExclusionsResponse,
    ToolPolicy,
)
from teardrop.streaming import iter_sse_events


class _AgentMixin:
    async def run(
        self,
        message: str,
        *,
        thread_id: str | None = None,
        context: dict[str, Any] | None = None,
        payment_header: str | None = None,
        emit_ui: bool = True,
        tool_policy: ToolPolicy | None = None,
    ) -> AsyncIterator[SSEEvent]:
        http = await self._get_http()
        headers = await self._headers()
        headers["Accept"] = "text/event-stream"

        if payment_header:
            headers["X-Payment"] = payment_header

        req = AgentRunRequest(
            message=message,
            thread_id=thread_id or str(uuid.uuid4()),
            context=context,
            emit_ui=emit_ui,
            tool_policy=tool_policy,
        )
        body = req.model_dump(exclude_none=True)

        async with http.stream(
            "POST",
            f"{self._base_url}/agent/run",
            json=body,
            headers=headers,
            timeout=self._timeout,
        ) as resp:
            if not resp.is_success:
                await resp.aread()
                self._raise_for_status(resp)
            async for event in iter_sse_events(resp):
                yield event

    async def get_agent_tools(self) -> list[AgentTool]:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/agent/tools",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        data = resp.json()
        if isinstance(data, list):
            return [AgentTool.model_validate(item) for item in data]
        return AgentToolsResponse.model_validate(data).tools

    async def get_decisions(
        self,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> AgentDecisionListResponse:
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        resp = await http.get(
            f"{self._base_url}/agent/decisions",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        return AgentDecisionListResponse.model_validate(resp.json())

    async def set_run_outcome(
        self,
        run_id: str,
        request: RunOutcomeRequest,
    ) -> RunOutcomeResponse:
        http = await self._get_http()
        resp = await http.patch(
            f"{self._base_url}/agent/runs/{run_id}/outcome",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return RunOutcomeResponse.model_validate(resp.json())

    async def dispatch_event(
        self, trigger_token: str, event_json: dict[str, Any]
    ) -> EventDispatchResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/agent/events/{trigger_token}",
            json=event_json,
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return EventDispatchResponse.model_validate(resp.json())

    async def get_tool_exclusions(self) -> ToolExclusionListResponse:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/agent/tool-exclusions",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return ToolExclusionListResponse.model_validate(resp.json())

    async def list_tool_exclusions(self) -> ToolExclusionsResponse:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/agent/tool-exclusions",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return ToolExclusionsResponse.model_validate(resp.json())

    async def add_tool_exclusion(self, tool_name: str) -> ToolExclusionActionResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/agent/tool-exclusions",
            json={"tool_name": tool_name},
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return ToolExclusionActionResponse.model_validate(resp.json())

    async def create_tool_exclusion(
        self, request: ToolExclusionRequest
    ) -> ToolExclusionCreateResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/agent/tool-exclusions",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return ToolExclusionCreateResponse.model_validate(resp.json())

    async def remove_tool_exclusion(self, tool_name: str) -> ToolExclusionRemovedResponse:
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/agent/tool-exclusions/{tool_name}",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return ToolExclusionRemovedResponse.model_validate(resp.json())

    async def delete_tool_exclusion(self, tool_name: str) -> None:
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/agent/tool-exclusions/{tool_name}",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)

    async def get_agent_decisions(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> AgentDecisionsResponse:
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        resp = await http.get(
            f"{self._base_url}/agent/decisions",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        return AgentDecisionsResponse.model_validate(resp.json())
