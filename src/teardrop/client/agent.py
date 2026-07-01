"""Agent-run client methods."""

from __future__ import annotations

import uuid
from typing import Any, AsyncIterator

from teardrop.models import AgentRunRequest, AgentTool, AgentToolsResponse, SSEEvent, ToolPolicy
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
        return AgentToolsResponse.model_validate(resp.json()).tools
