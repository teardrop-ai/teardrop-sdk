"""Tests for AsyncTeardropClient marketplace endpoint methods."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from teardrop.client import AsyncTeardropClient
from teardrop.exceptions import NotFoundError
from teardrop.models import (
    AuthorConfig,
    EarningsEntry,
    MarketplaceSubscription,
    MarketplaceTool,
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


# ─── get_marketplace_catalog ─────────────────────────────────────────────────


class TestGetMarketplaceCatalog:
    async def test_returns_parsed_marketplace_tools(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {"tools": [_TOOL, _TOOL], "next_cursor": None}
        )
        result = await client.get_marketplace_catalog()
        assert isinstance(result["tools"][0], MarketplaceTool)
        assert result["tools"][0].name == "acme/search"
        assert len(result["tools"]) == 2

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
        assert result["tools"] == []
        assert result["next_cursor"] is None


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


# ─── get_marketplace_balance ─────────────────────────────────────────────────


class TestGetMarketplaceBalance:
    async def test_returns_dict(self, client, mock_http):
        mock_http.get.return_value = _json_response({"balance_usdc": 50000})
        result = await client.get_marketplace_balance()
        assert isinstance(result, dict)
        assert result["balance_usdc"] == 50000


# ─── get_earnings ─────────────────────────────────────────────────────────────


class TestGetEarnings:
    async def test_paginated_response(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {"earnings": [_EARNINGS], "next_cursor": "xyz"}
        )
        result = await client.get_earnings()
        assert isinstance(result["earnings"][0], EarningsEntry)
        assert result["next_cursor"] == "xyz"

    async def test_legacy_flat_list_response(self, client, mock_http):
        # Server returns a raw array (legacy API shape) — client should wrap it
        mock_http.get.return_value = _json_response([_EARNINGS, _EARNINGS])
        result = await client.get_earnings()
        assert isinstance(result["earnings"][0], EarningsEntry)
        assert len(result["earnings"]) == 2
        assert result["next_cursor"] is None

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
    async def test_returns_dict(self, client, mock_http):
        mock_http.post.return_value = _json_response({"tx_hash": "0xABC"})
        request = WithdrawRequest(amount_usdc=500_000)
        result = await client.withdraw(request)
        assert result == {"tx_hash": "0xABC"}

    async def test_amount_in_body(self, client, mock_http):
        mock_http.post.return_value = _json_response({"tx_hash": "0xABC"})
        request = WithdrawRequest(amount_usdc=250_000)
        await client.withdraw(request)
        _, kwargs = mock_http.post.call_args
        assert kwargs["json"]["amount_usdc"] == 250_000


# ─── get_withdrawals ──────────────────────────────────────────────────────────


class TestGetWithdrawals:
    async def test_paginated_response_passthrough(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {"withdrawals": [{"id": "w-1"}], "next_cursor": None}
        )
        result = await client.get_withdrawals()
        assert result["withdrawals"] == [{"id": "w-1"}]
        assert result["next_cursor"] is None

    async def test_legacy_flat_list_response(self, client, mock_http):
        mock_http.get.return_value = _json_response([{"id": "w-1"}, {"id": "w-2"}])
        result = await client.get_withdrawals()
        assert result["withdrawals"] == [{"id": "w-1"}, {"id": "w-2"}]
        assert result["next_cursor"] is None

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
        mock_http.get.return_value = _json_response([_SUBSCRIPTION, _SUBSCRIPTION])
        result = await client.get_subscriptions()
        assert len(result) == 2
        assert isinstance(result[0], MarketplaceSubscription)

    async def test_empty_list(self, client, mock_http):
        mock_http.get.return_value = _json_response([])
        result = await client.get_subscriptions()
        assert result == []


# ─── unsubscribe ──────────────────────────────────────────────────────────────


class TestUnsubscribe:
    async def test_returns_none(self, client, mock_http):
        mock_http.delete.return_value = _json_response({}, status=204)
        result = await client.unsubscribe("sub-1")
        assert result is None

    async def test_correct_url(self, client, mock_http):
        mock_http.delete.return_value = _json_response({}, status=204)
        await client.unsubscribe("sub-abc")
        args, _ = mock_http.delete.call_args
        assert args[0] == "http://test/marketplace/subscriptions/sub-abc"

    async def test_404_raises_not_found(self, client, mock_http):
        mock_http.delete.return_value = _json_response({"detail": "Not found"}, status=404)
        with pytest.raises(NotFoundError):
            await client.unsubscribe("sub-missing")
