"""Wallet client methods."""

from __future__ import annotations

from typing import Any

from teardrop.client._core import _parse_list_response
from teardrop.models import AgentWallet, LinkWalletRequest, Wallet


class _WalletsMixin:
    async def link_wallet(self, request: LinkWalletRequest) -> Wallet:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/wallets/link",
            json=request.model_dump(),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return Wallet.model_validate(resp.json())

    async def get_wallets(self) -> list[Wallet]:
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/wallets/me", headers=await self._headers())
        self._raise_for_status(resp)
        return _parse_list_response(resp.json(), Wallet)

    async def delete_wallet(self, wallet_id: str) -> None:
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/wallets/{wallet_id}", headers=await self._headers()
        )
        self._raise_for_status(resp)

    async def provision_agent_wallet(self) -> AgentWallet:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/wallets/agent",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return AgentWallet.model_validate(resp.json())

    async def get_agent_wallet(self, *, include_balance: bool = False) -> AgentWallet:
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
        return AgentWallet.model_validate(resp.json())

    async def deactivate_agent_wallet(self) -> None:
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/wallets/agent",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
