"""A2A delegation client methods."""

from __future__ import annotations

from typing import Any

from teardrop.client._core import _quote_path_segment
from teardrop.models import (
    A2AAgentDeletedResponse,
    A2ADelegationEvent,
    AddTrustedAgentRequest,
    OrgA2AAgentResponse,
    TrustedAgent,
)


class _A2AMixin:
    async def add_trusted_agent(self, request: AddTrustedAgentRequest) -> OrgA2AAgentResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/a2a/agents",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return OrgA2AAgentResponse.model_validate(resp.json())

    async def list_trusted_agents(self) -> list[TrustedAgent]:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/a2a/agents",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        data = resp.json()
        if isinstance(data, list):
            return [TrustedAgent.model_validate(item) for item in data]
        return [TrustedAgent.model_validate(item) for item in data.get("items", [])]

    async def remove_trusted_agent(self, agent_id: str) -> A2AAgentDeletedResponse:
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/a2a/agents/{_quote_path_segment(agent_id)}",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return A2AAgentDeletedResponse.model_validate(resp.json())

    async def get_delegations(
        self,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> list[A2ADelegationEvent]:
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        resp = await http.get(
            f"{self._base_url}/a2a/delegations",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        data = resp.json()
        if isinstance(data, list):
            return [A2ADelegationEvent.model_validate(item) for item in data]
        return [A2ADelegationEvent.model_validate(item) for item in data.get("items", [])]
