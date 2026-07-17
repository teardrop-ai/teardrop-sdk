"""Tests for AsyncTeardropClient marketplace endpoint methods."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from teardrop.client import AsyncTeardropClient
from teardrop.exceptions import NotFoundError
from teardrop.models import (
    AuthorConfig,
    EarningsEntry,
    MarketplaceAuthorProfileResponse,
    MarketplaceBalanceResponse,
    MarketplaceCatalogDetailResponse,
    MarketplaceCatalogResponse,
    MarketplaceEarningsResponse,
    MarketplaceImportPreviewResponse,
    MarketplaceImportPublishResponse,
    MarketplaceImportPublishToolRequest,
    MarketplaceSubscription,
    MarketplaceSubscriptionListResponse,
    MarketplaceTool,
    MarketplaceWithdrawalHistoryItem,
    MarketplaceWithdrawalResponse,
    MarketplaceWithdrawalsListResponse,
    UnsubscribeResponse,
    WithdrawRequest,
)

from .conftest import _json_response

# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    return AsyncTeardropClient("http://test", token="tok.en.sig")


@pytest.fixture
def mock_http(client):
    mock = AsyncMock()
    mock.is_closed = False
    client._http = mock
    with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
        yield mock


_TOOL = {
    "name": "acme/search",
    "description": "Search the web",
    "input_schema": {},
    "cost_usdc": 100,
    "author": "Acme",
    "author_slug": "acme",
    "tool_type": "webhook",
}

_AUTHOR_CONFIG = {
    "org_id": "org-1",
    "settlement_wallet": "0xSETTLE",
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}

_EARNINGS = {
    "id": "e-1",
    "tool_name": "acme/search",
    "total_cost_usdc": 10000,
    "caller_org_id": "org-2",
    "author_share_usdc": 8000,
    "platform_share_usdc": 2000,
    "status": "settled",
    "created_at": "2026-01-01T00:00:00Z",
}

_SUBSCRIPTION = {
    "id": "sub-1",
    "org_id": "org-1",
    "qualified_tool_name": "acme/search",
    "is_active": True,
    "subscribed_at": "2026-01-01T00:00:00Z",
}

_SUMMARY = {
    "name": "search",
    "qualified_name": "acme/search",
    "tool_name": "search",
    "display_name": "Search",
    "description": "Search the web",
    "short_description": "Web search",
    "input_schema": {},
    "cost_usdc": 100,
    "tool_type": "webhook",
    "category": "search",
    "total_calls": 12,
    "reputation_score": 0.9,
    "health_status": "healthy",
    "is_healthy": True,
    "author": "Acme",
    "author_slug": "acme",
}


# ─── get_marketplace_catalog ─────────────────────────────────────────────────


class TestGetMarketplaceCatalog:
    async def test_returns_parsed_marketplace_tools(self, client, mock_http):
        mock_http.get.return_value = _json_response({"tools": [_TOOL, _TOOL], "next_cursor": None})
        result = await client.get_marketplace_catalog()
        assert isinstance(result, MarketplaceCatalogResponse)
        assert isinstance(result.tools[0], MarketplaceTool)
        assert result.tools[0].name == "acme/search"
        assert result.tools[0].tool_type == "webhook"
        assert len(result.tools) == 2

    async def test_no_auth_header_sent(self, client, mock_http):
        mock_http.get.return_value = _json_response({"tools": [], "next_cursor": None})
        await client.get_marketplace_catalog()
        _, kwargs = mock_http.get.call_args
        # Unauthenticated endpoint — headers kwarg should NOT be present
        assert "headers" not in kwargs

    async def test_org_slug_param_forwarded(self, client, mock_http):
        mock_http.get.return_value = _json_response({"tools": [], "next_cursor": None})
        await client.get_marketplace_catalog(org_slug="platform")
        _, kwargs = mock_http.get.call_args
        assert kwargs["params"]["org_slug"] == "platform"

    async def test_pagination_params_forwarded(self, client, mock_http):
        mock_http.get.return_value = _json_response({"tools": [], "next_cursor": None})
        await client.get_marketplace_catalog(limit=10, cursor="page2")
        _, kwargs = mock_http.get.call_args
        assert kwargs["params"]["limit"] == 10
        assert kwargs["params"]["cursor"] == "page2"

    async def test_sort_param_forwarded(self, client, mock_http):
        mock_http.get.return_value = _json_response({"tools": [], "next_cursor": None})
        await client.get_marketplace_catalog(sort="price_asc")
        _, kwargs = mock_http.get.call_args
        assert kwargs["params"]["sort"] == "price_asc"

    async def test_empty_tools_list(self, client, mock_http):
        mock_http.get.return_value = _json_response({"tools": [], "next_cursor": None})
        result = await client.get_marketplace_catalog()
        assert isinstance(result, MarketplaceCatalogResponse)
        assert result.tools == []
        assert result.next_cursor is None


# ─── set_author_config ───────────────────────────────────────────────────────


class TestSetAuthorConfig:
    async def test_returns_author_config(self, client, mock_http):
        mock_http.post.return_value = _json_response(_AUTHOR_CONFIG)
        result = await client.set_author_config("0xSETTLE")
        assert isinstance(result, AuthorConfig)
        assert result.settlement_wallet == "0xSETTLE"

    async def test_settlement_wallet_in_body(self, client, mock_http):
        mock_http.post.return_value = _json_response(_AUTHOR_CONFIG)
        await client.set_author_config("0xABC")
        _, kwargs = mock_http.post.call_args
        assert kwargs["json"] == {"settlement_wallet": "0xABC"}


# ─── get_author_config ────────────────────────────────────────────────────────


class TestGetAuthorConfig:
    async def test_returns_author_config(self, client, mock_http):
        mock_http.get.return_value = _json_response(_AUTHOR_CONFIG)
        result = await client.get_author_config()
        assert isinstance(result, AuthorConfig)
        assert result.org_id == "org-1"

    async def test_404_raises_not_found(self, client, mock_http):
        mock_http.get.return_value = _json_response({"detail": "Not found"}, status=404)
        with pytest.raises(NotFoundError):
            await client.get_author_config()


class TestMarketplaceDiscovery:
    async def test_catalog_detail_uses_wrapped_tool(self, client, mock_http):
        mock_http.get.return_value = _json_response({"tool": _SUMMARY})
        result = await client.get_marketplace_catalog_detail("acme", "search")
        assert isinstance(result, MarketplaceCatalogDetailResponse)
        assert result.tool.qualified_name == "acme/search"

    async def test_author_profile_parses_spec_shape(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {
                "org_slug": "acme",
                "org_name": "Acme",
                "tool_count": 1,
                "total_calls": 12,
                "tools": [_SUMMARY],
                "next_cursor": None,
            }
        )
        result = await client.get_author_profile("acme")
        assert isinstance(result, MarketplaceAuthorProfileResponse)
        assert result.tools[0].name == "search"


# ─── get_marketplace_balance ─────────────────────────────────────────────────


class TestGetMarketplaceBalance:
    async def test_returns_balance_response(self, client, mock_http):
        mock_http.get.return_value = _json_response({"org_id": "org-1", "balance_usdc": 50000})
        result = await client.get_marketplace_balance()
        assert isinstance(result, MarketplaceBalanceResponse)
        assert result.balance_usdc == 50000


# ─── get_earnings ─────────────────────────────────────────────────────────────


class TestGetEarnings:
    async def test_paginated_response(self, client, mock_http):
        mock_http.get.return_value = _json_response({"earnings": [_EARNINGS], "next_cursor": "xyz"})
        result = await client.get_earnings()
        assert isinstance(result, MarketplaceEarningsResponse)
        assert isinstance(result.earnings[0], EarningsEntry)
        assert result.next_cursor == "xyz"

    async def test_legacy_flat_list_response(self, client, mock_http):
        # Server returns a raw array (legacy API shape) — test uses envelope
        mock_http.get.return_value = _json_response(
            {"earnings": [_EARNINGS, _EARNINGS], "next_cursor": None}
        )
        result = await client.get_earnings()
        assert isinstance(result, MarketplaceEarningsResponse)
        assert isinstance(result.earnings[0], EarningsEntry)
        assert len(result.earnings) == 2
        assert result.next_cursor is None

    async def test_filter_params_forwarded(self, client, mock_http):
        mock_http.get.return_value = _json_response({"earnings": [], "next_cursor": None})
        await client.get_earnings(tool_name="acme/search", limit=5)
        _, kwargs = mock_http.get.call_args
        assert kwargs["params"]["tool_name"] == "acme/search"
        assert kwargs["params"]["limit"] == 5

    async def test_cursor_param_forwarded(self, client, mock_http):
        mock_http.get.return_value = _json_response({"earnings": [], "next_cursor": None})
        await client.get_earnings(cursor="page2")
        _, kwargs = mock_http.get.call_args
        assert kwargs["params"]["cursor"] == "page2"


# ─── withdraw ─────────────────────────────────────────────────────────────────


class TestWithdraw:
    async def test_returns_withdrawal_response(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {
                "id": "w-1",
                "org_id": "org-1",
                "amount_usdc": 500_000,
                "wallet": "0xWALLET",
                "tx_hash": "0xABC",
                "status": "pending",
                "created_at": "2026-01-01T00:00:00Z",
            }
        )
        request = WithdrawRequest(amount_usdc=500_000)
        result = await client.withdraw(request)
        assert isinstance(result, MarketplaceWithdrawalResponse)
        assert result.tx_hash == "0xABC"

    async def test_amount_in_body(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {
                "id": "w-1",
                "org_id": "org-1",
                "amount_usdc": 250_000,
                "wallet": "0xWALLET",
                "status": "pending",
                "created_at": "2026-01-01T00:00:00Z",
            }
        )
        request = WithdrawRequest(amount_usdc=250_000)
        await client.withdraw(request)
        _, kwargs = mock_http.post.call_args
        assert kwargs["json"]["amount_usdc"] == 250_000


# ─── get_withdrawals ──────────────────────────────────────────────────────────


class TestGetWithdrawals:
    async def test_paginated_response(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {
                "withdrawals": [
                    {
                        "id": "w-1",
                        "amount_usdc": 100,
                        "wallet": "0xWALLET",
                        "status": "completed",
                        "created_at": "2026-01-01T00:00:00Z",
                    }
                ],
                "next_cursor": None,
            }
        )
        result = await client.get_withdrawals()
        assert isinstance(result, MarketplaceWithdrawalsListResponse)
        assert isinstance(result.withdrawals[0], MarketplaceWithdrawalHistoryItem)
        assert result.withdrawals[0].id == "w-1"
        assert result.next_cursor is None

    async def test_legacy_flat_list_response(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {
                "withdrawals": [
                    {
                        "id": "w-1",
                        "amount_usdc": 100,
                        "wallet": "0xWALLET",
                        "status": "completed",
                        "created_at": "2026-01-01T00:00:00Z",
                    },
                    {
                        "id": "w-2",
                        "amount_usdc": 200,
                        "wallet": "0xWALLET",
                        "status": "completed",
                        "created_at": "2026-01-01T00:00:00Z",
                    },
                ],
                "next_cursor": None,
            }
        )
        result = await client.get_withdrawals()
        assert isinstance(result, MarketplaceWithdrawalsListResponse)
        assert len(result.withdrawals) == 2
        assert result.next_cursor is None

    async def test_limit_param_forwarded(self, client, mock_http):
        mock_http.get.return_value = _json_response({"withdrawals": [], "next_cursor": None})
        await client.get_withdrawals(limit=5)
        _, kwargs = mock_http.get.call_args
        assert kwargs["params"]["limit"] == 5

    async def test_cursor_param_forwarded(self, client, mock_http):
        mock_http.get.return_value = _json_response({"withdrawals": [], "next_cursor": None})
        await client.get_withdrawals(cursor="next-page")
        _, kwargs = mock_http.get.call_args
        assert kwargs["params"]["cursor"] == "next-page"


# ─── subscribe ────────────────────────────────────────────────────────────────


class TestSubscribe:
    async def test_returns_marketplace_subscription(self, client, mock_http):
        mock_http.post.return_value = _json_response(_SUBSCRIPTION)
        result = await client.subscribe("acme/search")
        assert isinstance(result, MarketplaceSubscription)
        assert result.qualified_tool_name == "acme/search"

    async def test_tool_name_in_body(self, client, mock_http):
        mock_http.post.return_value = _json_response(_SUBSCRIPTION)
        await client.subscribe("acme/search")
        _, kwargs = mock_http.post.call_args
        assert kwargs["json"] == {"qualified_tool_name": "acme/search"}


# ─── get_subscriptions ────────────────────────────────────────────────────────


class TestGetSubscriptions:
    async def test_returns_list_of_subscriptions(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {"subscriptions": [_SUBSCRIPTION, _SUBSCRIPTION], "next_cursor": None}
        )
        result = await client.get_subscriptions()
        assert isinstance(result, MarketplaceSubscriptionListResponse)
        assert len(result.subscriptions) == 2
        assert isinstance(result.subscriptions[0], MarketplaceSubscription)

    async def test_empty_list(self, client, mock_http):
        mock_http.get.return_value = _json_response({"subscriptions": [], "next_cursor": None})
        result = await client.get_subscriptions()
        assert isinstance(result, MarketplaceSubscriptionListResponse)
        assert result.subscriptions == []


# ─── unsubscribe ──────────────────────────────────────────────────────────────


class TestUnsubscribe:
    async def test_returns_unsubscribe_response(self, client, mock_http):
        mock_http.delete.return_value = _json_response({"unsubscribed": True})
        result = await client.unsubscribe("sub-1")
        assert isinstance(result, UnsubscribeResponse)
        assert result.unsubscribed is True

    async def test_correct_url(self, client, mock_http):
        mock_http.delete.return_value = _json_response({"unsubscribed": True})
        await client.unsubscribe("sub-abc")
        args, _ = mock_http.delete.call_args
        assert args[0] == "http://test/marketplace/subscriptions/sub-abc"

    async def test_404_raises_not_found(self, client, mock_http):
        mock_http.delete.return_value = _json_response({"detail": "Not found"}, status=404)
        with pytest.raises(NotFoundError):
            await client.unsubscribe("sub-missing")


class TestMarketplaceFeedbackAndImport:
    async def test_submit_feedback_sends_spec_request(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {
                "id": "feedback-1",
                "run_id": "run-1",
                "qualified_tool_name": "acme/search",
                "rating": 1,
                "created_at": "2026-07-17T00:00:00Z",
            },
            status=201,
        )
        result = await client.submit_feedback(
            "acme", "search", run_id="run-1", rating=1, comment="Useful"
        )
        assert result.run_id == "run-1"
        args, kwargs = mock_http.post.call_args
        assert args[0] == "http://test/marketplace/tools/acme/search/feedback"
        assert kwargs["json"] == {"run_id": "run-1", "rating": 1, "comment": "Useful"}

    async def test_import_preview_sends_server_id(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {
                "server_id": "srv-1",
                "slots_remaining": 4,
                "can_publish": True,
                "tools": [],
                "errors": [],
            }
        )
        result = await client.import_preview("srv-1", tool_names=["search"])
        assert isinstance(result, MarketplaceImportPreviewResponse)
        args, kwargs = mock_http.post.call_args
        assert args[0] == "http://test/marketplace/import/preview"
        assert kwargs["json"] == {"server_id": "srv-1", "tool_names": ["search"]}

    async def test_import_publish_sends_server_id_and_tools(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {"server_id": "srv-1", "created": [], "errors": []}
        )
        tool = MarketplaceImportPublishToolRequest(
            remote_tool_name="search",
            name="search",
            description="Search the web",
        )
        result = await client.import_publish("srv-1", [tool])
        assert isinstance(result, MarketplaceImportPublishResponse)
        args, kwargs = mock_http.post.call_args
        assert args[0] == "http://test/marketplace/import/publish"
        assert kwargs["json"]["server_id"] == "srv-1"
        assert kwargs["json"]["tools"][0]["remote_tool_name"] == "search"
