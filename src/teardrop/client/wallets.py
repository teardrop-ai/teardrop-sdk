"""Wallet client methods."""

from __future__ import annotations

from typing import Any

from teardrop.client._core import _quote_path_segment
from teardrop.models import (
    AgentWalletDeactivatedResponse,
    AgentWalletResponse,
    LinkWalletRequest,
    LinkWalletResponse,
    WalletDeletedResponse,
    WalletItem,
)


class _WalletsMixin:
    async def link_wallet(self, request: LinkWalletRequest) -> LinkWalletResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/wallets/link",
            json=request.model_dump(),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return LinkWalletResponse.model_validate(resp.json())

    async def get_wallets(self) -> list[WalletItem]:
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/wallets/me", headers=await self._headers())
        self._raise_for_status(resp)
        data = resp.json()
        if isinstance(data, list):
            return [WalletItem.model_validate(item) for item in data]
        return [WalletItem.model_validate(item) for item in data.get("items", [])]

    async def delete_wallet(self, wallet_id: str) -> WalletDeletedResponse:
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/wallets/{_quote_path_segment(wallet_id)}",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return WalletDeletedResponse.model_validate(resp.json())

    async def provision_agent_wallet(self) -> AgentWalletResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/wallets/agent",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return AgentWalletResponse.model_validate(resp.json())

    async def get_agent_wallet(self, *, include_balance: bool = False) -> AgentWalletResponse:
        http = await self._get_http()
        params: dict[str, Any] = {}
        if include_balance:
            params["include_balance"] = "true"
        resp = await http.get(
            f"{self._base_url}/wallets/agent",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        return AgentWalletResponse.model_validate(resp.json())

    async def deactivate_agent_wallet(self) -> AgentWalletDeactivatedResponse:
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/wallets/agent",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return AgentWalletDeactivatedResponse.model_validate(resp.json())
