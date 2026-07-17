"""Marketplace client methods."""

from __future__ import annotations

from typing import Any

from teardrop.client._core import _quote_path_segment
from teardrop.models import (
    MarketplaceAuthorConfigResponse,
    MarketplaceAuthorProfileResponse,
    MarketplaceBalanceResponse,
    MarketplaceCatalogDetailResponse,
    MarketplaceCatalogResponse,
    MarketplaceEarningsByToolResponse,
    MarketplaceEarningsResponse,
    MarketplaceImportPreviewRequest,
    MarketplaceImportPreviewResponse,
    MarketplaceImportPublishRequest,
    MarketplaceImportPublishResponse,
    MarketplaceImportPublishToolRequest,
    MarketplaceSubscriptionListResponse,
    MarketplaceSubscriptionResponse,
    MarketplaceWithdrawalResponse,
    MarketplaceWithdrawalsListResponse,
    RunFeedbackRequest,
    RunFeedbackResponse,
    UnsubscribeResponse,
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
    ) -> MarketplaceCatalogResponse:
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
        return MarketplaceCatalogResponse.model_validate(resp.json())

    async def get_marketplace_catalog_detail(
        self, org_slug: str, tool_name: str
    ) -> MarketplaceCatalogDetailResponse:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/marketplace/catalog/{_quote_path_segment(org_slug)}/{_quote_path_segment(tool_name)}",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return MarketplaceCatalogDetailResponse.model_validate(resp.json())

    async def set_author_config(self, settlement_wallet: str) -> MarketplaceAuthorConfigResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/marketplace/author-config",
            json={"settlement_wallet": settlement_wallet},
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return MarketplaceAuthorConfigResponse.model_validate(resp.json())

    async def get_author_config(self) -> MarketplaceAuthorConfigResponse:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/marketplace/author-config", headers=await self._headers()
        )
        self._raise_for_status(resp)
        return MarketplaceAuthorConfigResponse.model_validate(resp.json())

    async def get_author_profile(self, org_slug: str) -> MarketplaceAuthorProfileResponse:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/marketplace/authors/{_quote_path_segment(org_slug)}",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return MarketplaceAuthorProfileResponse.model_validate(resp.json())

    async def get_marketplace_balance(self) -> MarketplaceBalanceResponse:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/marketplace/balance", headers=await self._headers()
        )
        self._raise_for_status(resp)
        return MarketplaceBalanceResponse.model_validate(resp.json())

    async def get_earnings(
        self,
        *,
        limit: int = 20,
        tool_name: str | None = None,
        cursor: str | None = None,
    ) -> MarketplaceEarningsResponse:
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
        return MarketplaceEarningsResponse.model_validate(resp.json())

    async def get_earnings_by_tool(
        self,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> MarketplaceEarningsByToolResponse:
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        resp = await http.get(
            f"{self._base_url}/marketplace/earnings/by-tool",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        return MarketplaceEarningsByToolResponse.model_validate(resp.json())

    async def withdraw(self, request: WithdrawRequest) -> MarketplaceWithdrawalResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/marketplace/withdraw",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return MarketplaceWithdrawalResponse.model_validate(resp.json())

    async def get_withdrawals(
        self,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> MarketplaceWithdrawalsListResponse:
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
        return MarketplaceWithdrawalsListResponse.model_validate(resp.json())

    async def subscribe(self, qualified_tool_name: str) -> MarketplaceSubscriptionResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/marketplace/subscriptions",
            json={"qualified_tool_name": qualified_tool_name},
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return MarketplaceSubscriptionResponse.model_validate(resp.json())

    async def get_subscriptions(self) -> MarketplaceSubscriptionListResponse:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/marketplace/subscriptions",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return MarketplaceSubscriptionListResponse.model_validate(resp.json())

    async def unsubscribe(self, subscription_id: str) -> UnsubscribeResponse:
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/marketplace/subscriptions/{_quote_path_segment(subscription_id)}",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return UnsubscribeResponse.model_validate(resp.json())

    async def submit_feedback(
        self,
        org_slug: str,
        tool_name: str,
        *,
        run_id: str,
        rating: int,
        comment: str = "",
    ) -> RunFeedbackResponse:
        http = await self._get_http()
        request = RunFeedbackRequest(run_id=run_id, rating=rating, comment=comment)
        resp = await http.post(
            f"{self._base_url}/marketplace/tools/{_quote_path_segment(org_slug)}/{_quote_path_segment(tool_name)}/feedback",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return RunFeedbackResponse.model_validate(resp.json())

    async def import_preview(
        self,
        server_id: str,
        *,
        tool_names: list[str] | None = None,
    ) -> MarketplaceImportPreviewResponse:
        http = await self._get_http()
        request = MarketplaceImportPreviewRequest(server_id=server_id, tool_names=tool_names)
        resp = await http.post(
            f"{self._base_url}/marketplace/import/preview",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return MarketplaceImportPreviewResponse.model_validate(resp.json())

    async def import_publish(
        self,
        server_id: str,
        tools: list[MarketplaceImportPublishToolRequest],
    ) -> MarketplaceImportPublishResponse:
        http = await self._get_http()
        request = MarketplaceImportPublishRequest(server_id=server_id, tools=tools)
        resp = await http.post(
            f"{self._base_url}/marketplace/import/publish",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return MarketplaceImportPublishResponse.model_validate(resp.json())
