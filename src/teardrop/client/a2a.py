"""A2A delegation client methods."""

from __future__ import annotations

from typing import Any

from teardrop.client._core import _parse_list_response
from teardrop.models import AddTrustedAgentRequest, TrustedAgent


class _A2AMixin:
    async def add_trusted_agent(self, request: AddTrustedAgentRequest) -> TrustedAgent:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/a2a/agents",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return TrustedAgent.model_validate(resp.json())

    async def list_trusted_agents(self) -> list[TrustedAgent]:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/a2a/agents",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return _parse_list_response(resp.json(), TrustedAgent)

    async def remove_trusted_agent(self, agent_id: str) -> None:
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/a2a/agents/{agent_id}",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)

    async def get_delegations(self, *, limit: int = 20) -> list[dict[str, Any]]:
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        resp = await http.get(
            f"{self._base_url}/a2a/delegations",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        return resp.json()
