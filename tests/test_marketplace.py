"""Tests for AsyncTeardropClient marketplace endpoint methods."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from teardrop.client import AsyncTeardropClient
from teardrop.exceptions import NotFoundError
from teardrop.models import (
    AuthorConfig,
    EarningsEntry,
    MarketplaceImportPreviewRequest,
    MarketplaceImportPreviewResponse,
    MarketplaceImportPublishRequest,
    MarketplaceImportPublishResponse,
    MarketplaceImportPublishToolRequest,
    MarketplaceSubscription,
    MarketplaceTool,
    MarketplaceToolFeedbackResponse,
    RunFeedbackRequest,
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


# ─── get_marketplace_catalog ─────────────────────────────────────────────────


class TestGetMarketplaceCatalog:
    async def test_returns_parsed_marketplace_tools(self, client, mock_http):
        mock_http.get.return_value = _json_response({"tools": [_TOOL, _TOOL], "next_cursor": None})
        result = await client.get_marketplace_catalog()
        assert isinstance(result["tools"][0], MarketplaceTool)
        assert result["tools"][0].name == "acme/search"
        assert result["tools"][0].tool_type == "webhook"
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
        mock_http.get.return_value = _json_response({"earnings": [_EARNINGS], "next_cursor": "xyz"})
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


# ─── get_marketplace_catalog_detail ───────────────────────────────────────────


class TestGetMarketplaceCatalogDetail:
    async def test_returns_marketplace_tool(self, client, mock_http):
        mock_http.get.return_value = _json_response(_TOOL)
        result = await client.get_marketplace_catalog_detail("acme", "search")
        assert isinstance(result, MarketplaceTool)
        assert result.name == "acme/search"

    async def test_calls_expected_url(self, client, mock_http):
        mock_http.get.return_value = _json_response(_TOOL)
        await client.get_marketplace_catalog_detail("acme", "search")
        args, kwargs = mock_http.get.call_args
        assert args[0] == "http://test/marketplace/catalog/acme/search"
        assert "headers" not in kwargs

    async def test_404_raises_not_found(self, client, mock_http):
        mock_http.get.return_value = _json_response({"detail": "Not found"}, status=404)
        with pytest.raises(NotFoundError):
            await client.get_marketplace_catalog_detail("acme", "missing")


# ─── get_marketplace_author_profile ───────────────────────────────────────────


class TestGetMarketplaceAuthorProfile:
    async def test_parses_tools_list(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {"org_slug": "acme", "display_name": "Acme", "tools": [_TOOL]}
        )
        result = await client.get_marketplace_author_profile("acme")
        assert isinstance(result["tools"][0], MarketplaceTool)
        assert result["display_name"] == "Acme"

    async def test_params_forwarded(self, client, mock_http):
        mock_http.get.return_value = _json_response({"tools": []})
        await client.get_marketplace_author_profile("acme", sort="popularity", limit=10)
        args, kwargs = mock_http.get.call_args
        assert args[0] == "http://test/marketplace/authors/acme"
        assert kwargs["params"] == {"sort": "popularity", "limit": 10}


# ─── preview_marketplace_import ───────────────────────────────────────────────


class TestPreviewMarketplaceImport:
    async def test_returns_response_model(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {
                "server_id": "srv-123",
                "slots_remaining": 5,
                "can_publish": True,
                "blockers": [],
                "tools": [
                    {
                        "remote_tool_name": "fetch_webpage",
                        "proposed_name": "fetch_webpage",
                        "description": "Download webpage content.",
                        "marketplace_description": "Download webpage content.",
                        "input_schema": {},
                        "output_schema": {},
                        "schema_status": {"input": "supported", "output": "synthesized"},
                        "dropped_schema_features": {"input": [], "output": []},
                        "name_adjusted": False,
                        "name_collision_resolved": False,
                        "quota_exceeded": False,
                        "publishable": True,
                        "suggested_base_price_usdc": 1000,
                        "category": "",
                        "warnings": [
                            "output_schema was synthesized "
                            "because the MCP server did not expose one"
                        ],
                    }
                ],
                "errors": [],
            }
        )
        result = await client.preview_marketplace_import(
            MarketplaceImportPreviewRequest(server_id="srv-123")
        )
        assert isinstance(result, MarketplaceImportPreviewResponse)
        assert result.server_id == "srv-123"
        assert result.slots_remaining == 5
        assert result.tools[0].remote_tool_name == "fetch_webpage"

    async def test_body_sent(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {
                "server_id": "srv-123",
                "slots_remaining": 5,
                "can_publish": True,
                "blockers": [],
                "tools": [],
                "errors": [],
            }
        )
        await client.preview_marketplace_import(
            MarketplaceImportPreviewRequest(server_id="mcp-1", tool_names=["search"])
        )
        args, kwargs = mock_http.post.call_args
        assert args[0] == "http://test/marketplace/import/preview"
        assert kwargs["json"] == {"server_id": "mcp-1", "tool_names": ["search"]}


# ─── publish_marketplace_import ───────────────────────────────────────────────


class TestPublishMarketplaceImport:
    async def test_returns_response_model(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {
                "server_id": "srv-123",
                "created": [
                    {
                        "remote_tool_name": "fetch_webpage",
                        "tool": {
                            "id": "tool-123",
                            "name": "fetch_webpage",
                            "org_id": "org-123",
                            "publish_as_mcp": True,
                            "mcp_server_id": "srv-123",
                            "mcp_tool_name": "fetch_webpage",
                            "base_price_usdc": 1000,
                        },
                    }
                ],
                "errors": [],
            }
        )
        request = MarketplaceImportPublishRequest(
            server_id="mcp-1",
            tools=[
                MarketplaceImportPublishToolRequest(
                    remote_tool_name="search",
                    name="web_search",
                    description="Search the web",
                )
            ],
        )
        result = await client.publish_marketplace_import(request)
        assert isinstance(result, MarketplaceImportPublishResponse)
        assert result.server_id == "srv-123"
        assert result.created[0].remote_tool_name == "fetch_webpage"
        assert result.created[0].tool.id == "tool-123"

    async def test_body_sent(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {
                "server_id": "srv-123",
                "created": [],
                "errors": [],
            }
        )
        request = MarketplaceImportPublishRequest(
            server_id="mcp-1",
            tools=[
                MarketplaceImportPublishToolRequest(
                    remote_tool_name="search",
                    name="web_search",
                    description="Search the web",
                )
            ],
        )
        await client.publish_marketplace_import(request)
        args, kwargs = mock_http.post.call_args
        assert args[0] == "http://test/marketplace/import/publish"
        assert kwargs["json"]["server_id"] == "mcp-1"
        assert kwargs["json"]["tools"][0]["remote_tool_name"] == "search"


# ─── submit_marketplace_tool_feedback ─────────────────────────────────────────


class TestSubmitMarketplaceToolFeedback:
    async def test_returns_response_model(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {
                "id": "feed-123",
                "run_id": "run-1",
                "qualified_tool_name": "acme/search",
                "rating": 1,
                "created_at": "2026-07-16T12:00:00.000000",
            }
        )
        result = await client.submit_marketplace_tool_feedback(
            "acme", "search", RunFeedbackRequest(run_id="run-1", rating=1)
        )
        assert isinstance(result, MarketplaceToolFeedbackResponse)
        assert result.id == "feed-123"
        assert result.qualified_tool_name == "acme/search"

    async def test_calls_expected_url_and_body(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {
                "id": "feed-123",
                "run_id": "run-1",
                "qualified_tool_name": "acme/search",
                "rating": -1,
                "created_at": "2026-07-16T12:00:00.000000",
            }
        )
        await client.submit_marketplace_tool_feedback(
            "acme", "search", RunFeedbackRequest(run_id="run-1", rating=-1, comment="slow")
        )
        args, kwargs = mock_http.post.call_args
        assert args[0] == "http://test/marketplace/tools/acme/search/feedback"
        assert kwargs["json"] == {"run_id": "run-1", "rating": -1, "comment": "slow"}

    async def test_404_raises_not_found(self, client, mock_http):
        mock_http.post.return_value = _json_response({"detail": "Not found"}, status=404)
        with pytest.raises(NotFoundError):
            await client.submit_marketplace_tool_feedback(
                "acme", "search", RunFeedbackRequest(run_id="run-1", rating=1)
            )
