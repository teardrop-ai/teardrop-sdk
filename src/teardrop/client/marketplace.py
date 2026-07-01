"""Marketplace client methods."""

from __future__ import annotations

from typing import Any

from teardrop.client._core import _parse_list_response
from teardrop.models import (
    AuthorConfig,
    EarningsEntry,
    MarketplaceSubscription,
    MarketplaceTool,
    WithdrawRequest,
)


class _MarketplaceMixin:
    async def get_marketplace_catalog(
        self,
        *,
        org_slug: str | None = None,
        sort: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        http = await self._get_http()
        params: dict[str, Any] = {}
        if org_slug is not None:
            params["org_slug"] = org_slug
        if sort is not None:
            params["sort"] = sort
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor
        resp = await http.get(f"{self._base_url}/marketplace/catalog", params=params)
        self._raise_for_status(resp)
        data = resp.json()
        data["tools"] = _parse_list_response(data, MarketplaceTool, item_container="tools")
        return data

    async def set_author_config(self, settlement_wallet: str) -> AuthorConfig:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/marketplace/author-config",
            json={"settlement_wallet": settlement_wallet},
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return AuthorConfig.model_validate(resp.json())

    async def get_author_config(self) -> AuthorConfig:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/marketplace/author-config", headers=await self._headers()
        )
        self._raise_for_status(resp)
        return AuthorConfig.model_validate(resp.json())

    async def get_marketplace_balance(self) -> dict[str, Any]:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/marketplace/balance", headers=await self._headers()
        )
        self._raise_for_status(resp)
        return resp.json()

    async def get_earnings(
        self,
        *,
        limit: int = 20,
        tool_name: str | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        if tool_name is not None:
            params["tool_name"] = tool_name
        if cursor is not None:
            params["cursor"] = cursor
        resp = await http.get(
            f"{self._base_url}/marketplace/earnings",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        data = resp.json()
        if isinstance(data, list):
            return {"earnings": _parse_list_response(data, EarningsEntry), "next_cursor": None}
        data["earnings"] = _parse_list_response(data, EarningsEntry, item_container="earnings")
        return data

    async def withdraw(self, request: WithdrawRequest) -> dict[str, Any]:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/marketplace/withdraw",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return resp.json()

    async def get_withdrawals(
        self,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        resp = await http.get(
            f"{self._base_url}/marketplace/withdrawals",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        data = resp.json()
        if isinstance(data, list):
            return {"withdrawals": data, "next_cursor": None}
        return data

    async def subscribe(self, qualified_tool_name: str) -> MarketplaceSubscription:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/marketplace/subscriptions",
            json={"qualified_tool_name": qualified_tool_name},
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return MarketplaceSubscription.model_validate(resp.json())

    async def get_subscriptions(self) -> list[MarketplaceSubscription]:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/marketplace/subscriptions",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return _parse_list_response(
            resp.json(), MarketplaceSubscription, item_container="subscriptions"
        )

    async def unsubscribe(self, subscription_id: str) -> None:
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/marketplace/subscriptions/{subscription_id}",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
