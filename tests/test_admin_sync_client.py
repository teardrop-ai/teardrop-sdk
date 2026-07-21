"""Tests for AdminTeardropClient sync facade delegation."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from teardrop.client._admin_sync import AdminTeardropClient
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
    TelemetryCompletenessResponse,
    ToolPricingDeleteResponse,
    ToolPricingOverrideRequest,
    ToolPricingOverrideResponse,
    UsageSummary,
    WithdrawalResetResponse,
)


class TestAdminSyncContextManager:
    def test_enter_exit_does_not_crash(self):
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            assert admin._portal is not None
        assert admin._portal is None

    def test_close_without_context_manager(self):
        admin = AdminTeardropClient("http://test", token="tok.en.sig")
        admin.close()
        assert admin._portal is None


class TestAdminSyncDelegation:
    # ── A2A ───────────────────────────────────────────────────────────────────

    def test_admin_add_a2a_agent(self):
        result = A2AAgentResponse(
            id="ta-1",
            org_id="org-1",
            agent_url="https://agent.dev",
            max_cost_usdc=0,
            require_x402=False,
            jwt_forward=False,
        )
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async, "admin_add_a2a_agent", new=AsyncMock(return_value=result)
            ) as mock:
                req = AdminCreateA2AAgentRequest(org_id="org-1", agent_url="https://agent.dev")
                assert admin.admin_add_a2a_agent(req) == result
                mock.assert_awaited_once_with(req)

    def test_admin_delete_a2a_agent(self):
        result = A2AAgentDeletedResponse(deleted="ta-1")
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async, "admin_delete_a2a_agent", new=AsyncMock(return_value=result)
            ) as mock:
                assert admin.admin_delete_a2a_agent("ta-1") == result
                mock.assert_awaited_once_with("ta-1")

    def test_admin_list_a2a_agents(self):
        result = [
            A2AAgentListItem(
                id="ta-1",
                org_id="org-1",
                agent_url="https://agent.dev",
                max_cost_usdc=0,
                require_x402=False,
                jwt_forward=False,
            )
        ]
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async, "admin_list_a2a_agents", new=AsyncMock(return_value=result)
            ) as mock:
                assert admin.admin_list_a2a_agents("org-1") == result
                mock.assert_awaited_once_with("org-1")

    # ── Billing ───────────────────────────────────────────────────────────────

    def test_admin_get_pending_settlements(self):
        result = PendingSettlementsResponse(items=[])
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async,
                "admin_get_pending_settlements",
                new=AsyncMock(return_value=result),
            ) as mock:
                assert admin.admin_get_pending_settlements(status="pending", limit=10) == result
                mock.assert_awaited_once_with(status="pending", limit=10)

    def test_admin_retry_settlement(self):
        result = SettlementRetryResponse(settlement_id="s-1", status="pending")
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async, "admin_retry_settlement", new=AsyncMock(return_value=result)
            ) as mock:
                assert admin.admin_retry_settlement("s-1") == result
                mock.assert_awaited_once_with("s-1")

    def test_admin_get_revenue(self):
        result = RevenueSummaryResponse(total_settlements=1, total_revenue_usdc=1000)
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async, "admin_get_revenue", new=AsyncMock(return_value=result)
            ) as mock:
                assert admin.admin_get_revenue(start="2026-01-01") == result
                mock.assert_awaited_once_with(start="2026-01-01", end=None)

    def test_admin_topup_credits(self):
        result = AdminTopupResponse(org_id="org-1", amount_usdc=1000, new_balance_usdc=2000)
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async, "admin_topup_credits", new=AsyncMock(return_value=result)
            ) as mock:
                req = AdminTopupRequest(org_id="org-1", amount_usdc=1000)
                assert admin.admin_topup_credits(req) == result
                mock.assert_awaited_once_with(req)

    # ── Identity ──────────────────────────────────────────────────────────────

    def test_admin_create_client_credentials(self):
        result = CreateClientCredentialsResponse(
            client_id="cid-1",
            client_secret="sec",
            org_id="org-1",
            created_at="2026-07-17T00:00:00Z",
        )
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async,
                "admin_create_client_credentials",
                new=AsyncMock(return_value=result),
            ) as mock:
                req = AdminCreateClientCredentialsRequest(org_id="org-1")
                assert admin.admin_create_client_credentials(req) == result
                mock.assert_awaited_once_with(req)

    def test_admin_create_org(self):
        result = CreateOrgResponse(id="org-1", name="Test", created_at="2026-07-17T00:00:00Z")
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async, "admin_create_org", new=AsyncMock(return_value=result)
            ) as mock:
                req = AdminCreateOrgRequest(name="Test")
                assert admin.admin_create_org(req) == result
                mock.assert_awaited_once_with(req)

    def test_admin_create_user(self):
        result = CreateUserResponse(
            id="u-1",
            email="u@e.com",
            org_id="org-1",
            role="user",
            created_at="2026-07-17T00:00:00Z",
        )
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async, "admin_create_user", new=AsyncMock(return_value=result)
            ) as mock:
                req = AdminCreateUserRequest(email="u@e.com", secret="password123", org_id="org-1")
                assert admin.admin_create_user(req) == result
                mock.assert_awaited_once_with(req)

    # ── Marketplace ───────────────────────────────────────────────────────────

    def test_admin_complete_withdrawal(self):
        result = MarketplaceCompleteWithdrawalResponse(
            status="completed", tx_hash="0xabc", completed_at="2026-07-17T00:00:00Z"
        )
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async, "admin_complete_withdrawal", new=AsyncMock(return_value=result)
            ) as mock:
                req = CompleteWithdrawalRequest(tx_hash="0xabc123def456")
                assert admin.admin_complete_withdrawal("wd-1", req) == result
                mock.assert_awaited_once_with("wd-1", req)

    def test_admin_process_withdrawal(self):
        result = AdminWithdrawalActionResponse(
            id="wd-1", org_id="org-1", amount_usdc=10000, status="settled"
        )
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async, "admin_process_withdrawal", new=AsyncMock(return_value=result)
            ) as mock:
                assert admin.admin_process_withdrawal("wd-1") == result
                mock.assert_awaited_once_with("wd-1")

    def test_admin_reset_withdrawal(self):
        result = WithdrawalResetResponse(id="wd-1", status="pending")
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async, "admin_reset_withdrawal", new=AsyncMock(return_value=result)
            ) as mock:
                assert admin.admin_reset_withdrawal("wd-1") == result
                mock.assert_awaited_once_with("wd-1")

    def test_admin_get_settlement_balance(self):
        result = SettlementBalanceResponse(
            account="settlement", address="0xSETTLEMENT", chain_id=8453, balance_usdc=100000
        )
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async,
                "admin_get_settlement_balance",
                new=AsyncMock(return_value=result),
            ) as mock:
                assert admin.admin_get_settlement_balance() == result
                mock.assert_awaited_once_with()

    def test_admin_sweep_marketplace(self):
        result = MarketplaceSweepResponse(processed=3)
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async, "admin_sweep_marketplace", new=AsyncMock(return_value=result)
            ) as mock:
                assert admin.admin_sweep_marketplace() == result
                mock.assert_awaited_once_with()

    def test_admin_sweep_retry_withdrawal(self):
        result = WithdrawalResetResponse(id="wd-1", status="pending")
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async,
                "admin_sweep_retry_withdrawal",
                new=AsyncMock(return_value=result),
            ) as mock:
                assert admin.admin_sweep_retry_withdrawal("wd-1") == result
                mock.assert_awaited_once_with("wd-1")

    def test_admin_get_sweep_status(self):
        result = SweepStatusResponse(pending=[], exhausted=[])
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async, "admin_get_sweep_status", new=AsyncMock(return_value=result)
            ) as mock:
                assert admin.admin_get_sweep_status() == result
                mock.assert_awaited_once_with()

    def test_admin_list_withdrawals(self):
        result = AdminWithdrawalListResponse(withdrawals=[])
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async, "admin_list_withdrawals", new=AsyncMock(return_value=result)
            ) as mock:
                assert admin.admin_list_withdrawals(org_id="org-1") == result
                mock.assert_awaited_once_with(org_id="org-1")

    # ── MCP ───────────────────────────────────────────────────────────────────

    def test_admin_list_mcp_servers(self):
        result = [
            McpServerResponse(
                id="srv-1",
                org_id="org-1",
                name="my_server",
                url="https://mcp.example.com/sse",
                auth_type="none",
                has_auth=False,
                auth_header_name=None,
                is_active=True,
                timeout_seconds=15,
                created_at="2026-07-17T00:00:00Z",
                updated_at="2026-07-17T00:00:00Z",
            )
        ]
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async, "admin_list_mcp_servers", new=AsyncMock(return_value=result)
            ) as mock:
                assert admin.admin_list_mcp_servers("org-1") == result
                mock.assert_awaited_once_with("org-1")

    # ── Memory ────────────────────────────────────────────────────────────────

    def test_admin_list_org_memories(self):
        result = AdminMemoryListResponse(items=[], total=0)
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async, "admin_list_org_memories", new=AsyncMock(return_value=result)
            ) as mock:
                assert admin.admin_list_org_memories("org-1", limit=25) == result
                mock.assert_awaited_once_with("org-1", limit=25)

    def test_admin_purge_org_memories(self):
        result = AdminMemoryPurgeResponse(status="purged", deleted=5)
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async, "admin_purge_org_memories", new=AsyncMock(return_value=result)
            ) as mock:
                assert admin.admin_purge_org_memories("org-1") == result
                mock.assert_awaited_once_with("org-1")

    # ── Orgs ──────────────────────────────────────────────────────────────────

    def test_admin_get_spending_config(self):
        result = OrgSpendingConfigResponse(
            org_id="org-1",
            balance_usdc=10000,
            spending_limit_usdc=50000,
            is_paused=False,
            daily_spend_usdc=1000,
        )
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async, "admin_get_spending_config", new=AsyncMock(return_value=result)
            ) as mock:
                assert admin.admin_get_spending_config("org-1") == result
                mock.assert_awaited_once_with("org-1")

    def test_admin_update_spending_config(self):
        result = OrgSpendingConfigResponse(
            org_id="org-1",
            balance_usdc=10000,
            spending_limit_usdc=50000,
            is_paused=True,
            daily_spend_usdc=1000,
        )
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async,
                "admin_update_spending_config",
                new=AsyncMock(return_value=result),
            ) as mock:
                req = SpendingConfigUpdate(is_paused=True)
                assert admin.admin_update_spending_config("org-1", req) == result
                mock.assert_awaited_once_with("org-1", req)

    # ── Pricing ───────────────────────────────────────────────────────────────

    def test_admin_upsert_tool_pricing(self):
        result = ToolPricingOverrideResponse(
            tool_name="web_search", cost_usdc=500, description="", updated=True
        )
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async, "admin_upsert_tool_pricing", new=AsyncMock(return_value=result)
            ) as mock:
                req = ToolPricingOverrideRequest(tool_name="web_search", cost_usdc=500)
                assert admin.admin_upsert_tool_pricing(req) == result
                mock.assert_awaited_once_with(req)

    def test_admin_delete_tool_pricing(self):
        result = ToolPricingDeleteResponse(tool_name="web_search", deleted=True)
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async, "admin_delete_tool_pricing", new=AsyncMock(return_value=result)
            ) as mock:
                assert admin.admin_delete_tool_pricing("web_search") == result
                mock.assert_awaited_once_with("web_search")

    # ── Tools ─────────────────────────────────────────────────────────────────

    def test_admin_list_tools(self):
        result = [
            OrgTool(
                id="tool-1",
                org_id="org-1",
                name="my_tool",
                description="Does a thing",
                input_schema={},
                output_schema=None,
                webhook_url="https://e.com/h",
                webhook_method="POST",
                mcp_server_id=None,
                mcp_tool_name=None,
                has_auth=False,
                timeout_seconds=15,
                is_active=True,
                publish_as_mcp=False,
                marketplace_description="",
                base_price_usdc=0,
                category="",
                created_at="2026-07-17T00:00:00Z",
                updated_at="2026-07-17T00:00:00Z",
            )
        ]
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async, "admin_list_tools", new=AsyncMock(return_value=result)
            ) as mock:
                assert admin.admin_list_tools("org-1") == result
                mock.assert_awaited_once_with("org-1")

    # ── Usage ─────────────────────────────────────────────────────────────────

    def test_admin_get_usage_org(self):
        result = UsageSummary()
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async, "admin_get_usage_org", new=AsyncMock(return_value=result)
            ) as mock:
                assert admin.admin_get_usage_org("org-1", start="2026-01-01") == result
                mock.assert_awaited_once_with("org-1", start="2026-01-01", end=None)

    def test_admin_get_usage_user(self):
        result = UsageSummary()
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async, "admin_get_usage_user", new=AsyncMock(return_value=result)
            ) as mock:
                assert admin.admin_get_usage_user("user-1") == result
                mock.assert_awaited_once_with("user-1", start=None, end=None)

    # ── Telemetry ─────────────────────────────────────────────────────────────

    def test_admin_get_telemetry_completeness(self):
        result = TelemetryCompletenessResponse(window_days=7, sources=[])
        with AdminTeardropClient("http://test", token="tok.en.sig") as admin:
            with patch.object(
                admin._async,
                "admin_get_telemetry_completeness",
                new=AsyncMock(return_value=result),
            ) as mock:
                assert admin.admin_get_telemetry_completeness(days=30) == result
                mock.assert_awaited_once_with(days=30)
