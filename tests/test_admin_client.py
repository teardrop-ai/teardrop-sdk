"""Tests for AsyncAdminTeardropClient admin endpoint methods."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from teardrop.client._admin_async import AsyncAdminTeardropClient
from teardrop.client.admin import _AdminMixin
from teardrop.models import (
    A2AAgentDeletedResponse,
    A2AAgentListItem,
    A2AAgentResponse,
    AdminCreateA2AAgentRequest,
    AdminCreateClientCredentialsRequest,
    AdminCreateOrgRequest,
    AdminCreateUserRequest,
    AdminMemoryListResponse,
    AdminMemoryPurgeResponse,
    AdminTopupRequest,
    AdminTopupResponse,
    AdminWithdrawalActionResponse,
    AdminWithdrawalListResponse,
    CompleteWithdrawalRequest,
    CreateClientCredentialsResponse,
    CreateOrgResponse,
    CreateUserResponse,
    MarketplaceCompleteWithdrawalResponse,
    MarketplaceSweepResponse,
    McpServerResponse,
    OrgSpendingConfigResponse,
    OrgTool,
    PendingSettlementsResponse,
    RevenueSummaryResponse,
    SettlementBalanceResponse,
    SettlementRetryResponse,
    SpendingConfigUpdate,
    SweepStatusResponse,
    ToolPricingDeleteResponse,
    ToolPricingOverrideRequest,
    ToolPricingOverrideResponse,
    UsageSummary,
    WithdrawalResetResponse,
)

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _json_response(body, *, status=200):
    import json

    import httpx

    return httpx.Response(
        status_code=status,
        content=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://test"),
    )


@pytest.fixture
def client():
    return AsyncAdminTeardropClient("http://test", token="tok.en.sig")


@pytest.fixture
def mock_http(client):
    mock = AsyncMock()
    mock.is_closed = False
    client._http = mock
    with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
        yield mock


def test_admin_surface_covers_every_spec_operation():
    spec = json.loads((Path(__file__).parents[1] / "spec" / "openapi.json").read_text())
    spec_operation_count = sum(
        1
        for path, item in spec["paths"].items()
        if path.startswith("/admin/")
        for method in item
        if method in {"get", "post", "patch", "put", "delete"}
    )
    implemented_methods = {
        name
        for name in dir(_AdminMixin)
        if name.startswith("admin_") and callable(getattr(_AdminMixin, name))
    }
    assert spec_operation_count == 28
    assert len(implemented_methods) == spec_operation_count


# ── Admin A2A ────────────────────────────────────────────────────────────────


class TestAdminA2A:
    async def test_admin_add_a2a_agent(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {
                "id": "ta-1",
                "org_id": "org-1",
                "agent_url": "https://agent.dev",
                "max_cost_usdc": 0,
                "require_x402": False,
                "jwt_forward": False,
            },
            status=201,
        )
        req = AdminCreateA2AAgentRequest(org_id="org-1", agent_url="https://agent.dev")
        result = await client.admin_add_a2a_agent(req)
        assert isinstance(result, A2AAgentResponse)
        assert result.agent_url == "https://agent.dev"
        assert result.org_id == "org-1"
        args, kwargs = mock_http.post.call_args
        assert args[0] == "http://test/admin/a2a/agents"
        assert kwargs["json"]["org_id"] == "org-1"

    async def test_admin_delete_a2a_agent(self, client, mock_http):
        mock_http.delete.return_value = _json_response({"deleted": "ta-1"})
        result = await client.admin_delete_a2a_agent("ta-1")
        assert isinstance(result, A2AAgentDeletedResponse)
        assert result.deleted == "ta-1"
        args, _ = mock_http.delete.call_args
        assert args[0] == "http://test/admin/a2a/agents/ta-1"

    async def test_admin_list_a2a_agents(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            [
                {
                    "id": "ta-1",
                    "org_id": "org-1",
                    "agent_url": "https://agent.dev",
                    "max_cost_usdc": 0,
                    "require_x402": False,
                    "jwt_forward": False,
                }
            ]
        )
        result = await client.admin_list_a2a_agents("org-1")
        assert len(result) == 1
        assert isinstance(result[0], A2AAgentListItem)
        assert result[0].agent_url == "https://agent.dev"
        args, _ = mock_http.get.call_args
        assert args[0] == "http://test/admin/a2a/agents/org-1"


# ── Admin Billing ────────────────────────────────────────────────────────────


class TestAdminBilling:
    async def test_admin_get_pending_settlements(self, client, mock_http):
        mock_http.get.return_value = _json_response({"items": [], "next_cursor": None})
        result = await client.admin_get_pending_settlements(limit=10, status="pending")
        assert isinstance(result, PendingSettlementsResponse)
        _, kwargs = mock_http.get.call_args
        assert kwargs["params"] == {"limit": 10, "status": "pending"}

    async def test_admin_retry_settlement(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {"settlement_id": "settle-1", "status": "pending"}
        )
        result = await client.admin_retry_settlement("settle-1")
        assert isinstance(result, SettlementRetryResponse)
        assert result.settlement_id == "settle-1"
        args, _ = mock_http.post.call_args
        assert args[0] == "http://test/admin/billing/pending/settle-1/retry"

    async def test_admin_get_revenue(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {"total_settlements": 5, "total_revenue_usdc": 50000}
        )
        result = await client.admin_get_revenue(start="2026-01-01", end="2026-07-17")
        assert isinstance(result, RevenueSummaryResponse)
        assert result.total_revenue_usdc == 50000
        assert result.total_settlements == 5
        _, kwargs = mock_http.get.call_args
        assert kwargs["params"] == {"start": "2026-01-01", "end": "2026-07-17"}

    async def test_admin_topup_credits(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {
                "org_id": "org-1",
                "amount_usdc": 10000,
                "new_balance_usdc": 20000,
                "created_at": "2026-07-17T00:00:00Z",
            }
        )
        req = AdminTopupRequest(org_id="org-1", amount_usdc=10000)
        result = await client.admin_topup_credits(req)
        assert isinstance(result, AdminTopupResponse)
        assert result.new_balance_usdc == 20000
        args, kwargs = mock_http.post.call_args
        assert args[0] == "http://test/admin/credits/topup"
        assert kwargs["json"]["org_id"] == "org-1"


# ── Admin Identity ───────────────────────────────────────────────────────────


class TestAdminIdentity:
    async def test_admin_create_client_credentials(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {
                "client_id": "cid-1",
                "client_secret": "secret-once",
                "org_id": "org-1",
                "created_at": "2026-07-17T00:00:00Z",
            },
            status=201,
        )
        req = AdminCreateClientCredentialsRequest(org_id="org-1")
        result = await client.admin_create_client_credentials(req)
        assert isinstance(result, CreateClientCredentialsResponse)
        assert result.client_secret == "secret-once"
        args, kwargs = mock_http.post.call_args
        assert args[0] == "http://test/admin/client-credentials"
        assert kwargs["json"]["org_id"] == "org-1"

    async def test_admin_create_org(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {"id": "org-new", "name": "New Org", "created_at": "2026-07-17T00:00:00Z"},
            status=201,
        )
        req = AdminCreateOrgRequest(name="New Org")
        result = await client.admin_create_org(req)
        assert isinstance(result, CreateOrgResponse)
        assert result.name == "New Org"
        args, kwargs = mock_http.post.call_args
        assert args[0] == "http://test/admin/orgs"

    async def test_admin_create_user(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {
                "id": "user-1",
                "email": "u@e.com",
                "org_id": "org-1",
                "role": "user",
                "created_at": "2026-07-17T00:00:00Z",
            },
            status=201,
        )
        req = AdminCreateUserRequest(email="u@e.com", secret="password123", org_id="org-1")
        result = await client.admin_create_user(req)
        assert isinstance(result, CreateUserResponse)
        assert result.email == "u@e.com"
        args, kwargs = mock_http.post.call_args
        assert args[0] == "http://test/admin/users"
        assert kwargs["json"]["role"] == "user"


# ── Admin Marketplace ────────────────────────────────────────────────────────


class TestAdminMarketplace:
    async def test_admin_complete_withdrawal(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {"status": "completed", "tx_hash": "0xabc123def456"}
        )
        req = CompleteWithdrawalRequest(tx_hash="0xabc123def456")
        result = await client.admin_complete_withdrawal("wd-1", req)
        assert isinstance(result, MarketplaceCompleteWithdrawalResponse)
        assert result.status == "completed"
        assert result.tx_hash == "0xabc123def456"
        args, _ = mock_http.post.call_args
        assert args[0] == "http://test/admin/marketplace/complete-withdrawal/wd-1"

    async def test_admin_process_withdrawal(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {"id": "wd-1", "org_id": "org-1", "amount_usdc": 10000, "status": "settled"}
        )
        result = await client.admin_process_withdrawal("wd-1")
        assert isinstance(result, AdminWithdrawalActionResponse)
        assert result.status == "settled"

    async def test_admin_reset_withdrawal(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {"id": "wd-1", "status": "pending", "reset_at": "2026-07-17T00:00:00Z"}
        )
        result = await client.admin_reset_withdrawal("wd-1")
        assert isinstance(result, WithdrawalResetResponse)
        assert result.status == "pending"

    async def test_admin_get_settlement_balance(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {
                "account": "settlement",
                "address": "0xSETTLEMENT",
                "chain_id": 8453,
                "balance_usdc": 100000,
            }
        )
        result = await client.admin_get_settlement_balance()
        assert isinstance(result, SettlementBalanceResponse)
        assert result.balance_usdc == 100000

    async def test_admin_sweep_marketplace(self, client, mock_http):
        mock_http.post.return_value = _json_response({"processed": 3})
        result = await client.admin_sweep_marketplace()
        assert isinstance(result, MarketplaceSweepResponse)
        assert result.processed == 3

    async def test_admin_sweep_retry_withdrawal(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {"id": "wd-1", "status": "pending", "reset_at": "2026-07-17T00:00:00Z"}
        )
        result = await client.admin_sweep_retry_withdrawal("wd-1")
        assert isinstance(result, WithdrawalResetResponse)
        args, _ = mock_http.post.call_args
        assert args[0] == "http://test/admin/marketplace/sweep-retry/wd-1"

    async def test_admin_get_sweep_status(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {
                "pending": [
                    {
                        "id": "wd-1",
                        "org_id": "org-1",
                        "amount_usdc": 10000,
                        "status": "pending",
                        "sweep_attempt_count": 0,
                        "created_at": "2026-07-17T00:00:00Z",
                    }
                ],
                "exhausted": [],
            }
        )
        result = await client.admin_get_sweep_status()
        assert isinstance(result, SweepStatusResponse)
        assert len(result.pending) == 1
        assert result.pending[0].org_id == "org-1"

    async def test_admin_list_withdrawals(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {
                "withdrawals": [
                    {
                        "id": "wd-1",
                        "org_id": "org-1",
                        "amount_usdc": 10000,
                        "wallet": "0xWALLET",
                        "status": "pending",
                        "created_at": "2026-07-17T00:00:00Z",
                    }
                ]
            }
        )
        result = await client.admin_list_withdrawals(org_id="org-1")
        assert isinstance(result, AdminWithdrawalListResponse)
        assert len(result.withdrawals) == 1
        assert result.withdrawals[0].wallet == "0xWALLET"
        _, kwargs = mock_http.get.call_args
        assert kwargs["params"] == {"org_id": "org-1"}


# ── Admin MCP ────────────────────────────────────────────────────────────────


class TestAdminMCP:
    async def test_admin_list_mcp_servers(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            [
                {
                    "id": "srv-1",
                    "org_id": "org-1",
                    "name": "my_server",
                    "url": "https://mcp.example.com/sse",
                    "auth_type": "none",
                    "has_auth": False,
                    "auth_header_name": None,
                    "is_active": True,
                    "timeout_seconds": 15,
                    "created_at": "2026-07-17T00:00:00Z",
                    "updated_at": "2026-07-17T00:00:00Z",
                }
            ]
        )
        result = await client.admin_list_mcp_servers("org-1")
        assert len(result) == 1
        assert isinstance(result[0], McpServerResponse)
        assert result[0].name == "my_server"
        args, _ = mock_http.get.call_args
        assert args[0] == "http://test/admin/mcp/servers/org-1"


# ── Admin Memory ─────────────────────────────────────────────────────────────


class TestAdminMemory:
    async def test_admin_list_org_memories(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {
                "items": [
                    {
                        "id": "m-1",
                        "content": "Remember this",
                        "user_id": "u-1",
                        "created_at": "2026-07-17T00:00:00Z",
                    }
                ],
                "total": 1,
            }
        )
        result = await client.admin_list_org_memories("org-1", limit=25)
        assert isinstance(result, AdminMemoryListResponse)
        assert result.total == 1
        assert result.items[0].user_id == "u-1"
        _, kwargs = mock_http.get.call_args
        assert kwargs["params"] == {"limit": 25}

    async def test_admin_purge_org_memories(self, client, mock_http):
        mock_http.delete.return_value = _json_response({"status": "purged", "deleted": 5})
        result = await client.admin_purge_org_memories("org-1")
        assert isinstance(result, AdminMemoryPurgeResponse)
        assert result.status == "purged"
        assert result.deleted == 5
        args, _ = mock_http.delete.call_args
        assert args[0] == "http://test/admin/memories/org/org-1"


# ── Admin Orgs ───────────────────────────────────────────────────────────────


class TestAdminOrgs:
    async def test_admin_get_spending_config(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {
                "org_id": "org-1",
                "balance_usdc": 10000,
                "spending_limit_usdc": 100000,
                "is_paused": False,
                "daily_spend_usdc": 1000,
            }
        )
        result = await client.admin_get_spending_config("org-1")
        assert isinstance(result, OrgSpendingConfigResponse)
        assert result.spending_limit_usdc == 100000
        args, _ = mock_http.get.call_args
        assert args[0] == "http://test/admin/orgs/org-1/spending"

    async def test_admin_update_spending_config(self, client, mock_http):
        mock_http.patch.return_value = _json_response(
            {
                "org_id": "org-1",
                "balance_usdc": 20000,
                "spending_limit_usdc": 50000,
                "is_paused": True,
                "daily_spend_usdc": 1000,
            }
        )
        req = SpendingConfigUpdate(spending_limit_usdc=50000, is_paused=True)
        result = await client.admin_update_spending_config("org-1", req)
        assert isinstance(result, OrgSpendingConfigResponse)
        args, kwargs = mock_http.patch.call_args
        assert args[0] == "http://test/admin/orgs/org-1/spending"
        assert kwargs["json"]["is_paused"] is True


# ── Admin Pricing ────────────────────────────────────────────────────────────


class TestAdminPricing:
    async def test_admin_upsert_tool_pricing(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {
                "tool_name": "web_search",
                "cost_usdc": 500,
                "description": "Custom price",
                "updated": True,
            }
        )
        req = ToolPricingOverrideRequest(
            tool_name="web_search", cost_usdc=500, description="Custom price"
        )
        result = await client.admin_upsert_tool_pricing(req)
        assert isinstance(result, ToolPricingOverrideResponse)
        assert result.cost_usdc == 500
        args, kwargs = mock_http.post.call_args
        assert args[0] == "http://test/admin/pricing/tools"
        assert kwargs["json"]["tool_name"] == "web_search"

    async def test_admin_delete_tool_pricing(self, client, mock_http):
        mock_http.delete.return_value = _json_response({"tool_name": "web_search", "deleted": True})
        result = await client.admin_delete_tool_pricing("web_search")
        assert isinstance(result, ToolPricingDeleteResponse)
        assert result.deleted is True
        args, _ = mock_http.delete.call_args
        assert args[0] == "http://test/admin/pricing/tools/web_search"


# ── Admin Tools ──────────────────────────────────────────────────────────────


class TestAdminTools:
    async def test_admin_list_tools(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            [
                {
                    "id": "tool-1",
                    "org_id": "org-1",
                    "name": "my_tool",
                    "description": "Does a thing",
                    "input_schema": {},
                    "output_schema": None,
                    "webhook_url": "https://example.com/hook",
                    "webhook_method": "POST",
                    "mcp_server_id": None,
                    "mcp_tool_name": None,
                    "has_auth": False,
                    "timeout_seconds": 15,
                    "is_active": True,
                    "publish_as_mcp": False,
                    "marketplace_description": "",
                    "base_price_usdc": 0,
                    "category": "",
                    "created_at": "2026-07-17T00:00:00Z",
                    "updated_at": "2026-07-17T00:00:00Z",
                }
            ]
        )
        result = await client.admin_list_tools("org-1")
        assert len(result) == 1
        assert isinstance(result[0], OrgTool)
        assert result[0].name == "my_tool"
        args, _ = mock_http.get.call_args
        assert args[0] == "http://test/admin/tools/org-1"


# ── Admin Usage ──────────────────────────────────────────────────────────────


class TestAdminUsage:
    async def test_admin_get_usage_org(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {"total_runs": 100, "total_cost_usdc": 50000, "by_tool": []}
        )
        result = await client.admin_get_usage_org("org-1", start="2026-01-01", end="2026-07-17")
        assert isinstance(result, UsageSummary)
        args, kwargs = mock_http.get.call_args
        assert args[0] == "http://test/admin/usage/org/org-1"
        assert kwargs["params"] == {"start": "2026-01-01", "end": "2026-07-17"}

    async def test_admin_get_usage_user(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {"total_runs": 50, "total_cost_usdc": 25000, "by_tool": []}
        )
        result = await client.admin_get_usage_user("user-1")
        assert isinstance(result, UsageSummary)
        args, _ = mock_http.get.call_args
        assert args[0] == "http://test/admin/usage/user-1"
