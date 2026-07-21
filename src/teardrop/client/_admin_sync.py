"""Synchronous admin client facade for Teardrop /admin/* endpoints."""

from __future__ import annotations

from typing import Any

from teardrop.client._admin_async import AsyncAdminTeardropClient
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
    CompleteWithdrawalResponse,
    CreateClientCredentialsResponse,
    CreateOrgResponse,
    CreateUserResponse,
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


class AdminTeardropClient:
    """Synchronous wrapper around ``AsyncAdminTeardropClient``.

    Requires an admin-privileged token.  Usage::

        with AdminTeardropClient("https://api.teardrop.dev", token="...") as admin:
            balance = admin.admin_get_settlement_balance()
    """

    def __init__(self, *args: Any, **kwargs: Any):
        self._async = AsyncAdminTeardropClient(*args, **kwargs)
        self._portal: Any | None = None
        self._portal_exit: Any | None = None

    def _ensure_portal(self) -> None:
        if self._portal is None:
            import anyio.from_thread

            cm = anyio.from_thread.start_blocking_portal()
            self._portal = cm.__enter__()
            self._portal_exit = cm.__exit__

    def _run(self, coro: Any) -> Any:
        self._ensure_portal()
        return self._portal.call(lambda: coro)  # type: ignore[union-attr]

    def close(self) -> None:
        if self._portal is not None:
            self._portal.call(lambda: self._async.close())  # type: ignore[union-attr]
            self._portal_exit(None, None, None)  # type: ignore[misc]
            self._portal = None
            self._portal_exit = None

    def __enter__(self):
        self._ensure_portal()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ── Admin A2A ─────────────────────────────────────────────────────────────

    def admin_add_a2a_agent(self, request: AdminCreateA2AAgentRequest) -> A2AAgentResponse:
        return self._run(self._async.admin_add_a2a_agent(request))

    def admin_delete_a2a_agent(self, agent_id: str) -> A2AAgentDeletedResponse:
        return self._run(self._async.admin_delete_a2a_agent(agent_id))

    def admin_list_a2a_agents(self, org_id: str) -> list[A2AAgentListItem]:
        return self._run(self._async.admin_list_a2a_agents(org_id))

    # ── Admin Billing ─────────────────────────────────────────────────────────

    def admin_get_pending_settlements(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> PendingSettlementsResponse:
        return self._run(self._async.admin_get_pending_settlements(status=status, limit=limit))

    def admin_retry_settlement(self, settlement_id: str) -> SettlementRetryResponse:
        return self._run(self._async.admin_retry_settlement(settlement_id))

    def admin_get_revenue(
        self, *, start: str | None = None, end: str | None = None
    ) -> RevenueSummaryResponse:
        return self._run(self._async.admin_get_revenue(start=start, end=end))

    def admin_topup_credits(self, request: AdminTopupRequest) -> AdminTopupResponse:
        return self._run(self._async.admin_topup_credits(request))

    # ── Admin Identity ────────────────────────────────────────────────────────

    def admin_create_client_credentials(
        self, request: AdminCreateClientCredentialsRequest
    ) -> CreateClientCredentialsResponse:
        return self._run(self._async.admin_create_client_credentials(request))

    def admin_create_org(self, request: AdminCreateOrgRequest) -> CreateOrgResponse:
        return self._run(self._async.admin_create_org(request))

    def admin_create_user(self, request: AdminCreateUserRequest) -> CreateUserResponse:
        return self._run(self._async.admin_create_user(request))

    # ── Admin Marketplace ─────────────────────────────────────────────────────

    def admin_complete_withdrawal(
        self, withdrawal_id: str, request: CompleteWithdrawalRequest
    ) -> CompleteWithdrawalResponse:
        return self._run(self._async.admin_complete_withdrawal(withdrawal_id, request))

    def admin_process_withdrawal(self, withdrawal_id: str) -> AdminWithdrawalActionResponse:
        return self._run(self._async.admin_process_withdrawal(withdrawal_id))

    def admin_reset_withdrawal(self, withdrawal_id: str) -> WithdrawalResetResponse:
        return self._run(self._async.admin_reset_withdrawal(withdrawal_id))

    def admin_get_settlement_balance(self) -> SettlementBalanceResponse:
        return self._run(self._async.admin_get_settlement_balance())

    def admin_sweep_marketplace(self) -> MarketplaceSweepResponse:
        return self._run(self._async.admin_sweep_marketplace())

    def admin_sweep_retry_withdrawal(self, withdrawal_id: str) -> WithdrawalResetResponse:
        return self._run(self._async.admin_sweep_retry_withdrawal(withdrawal_id))

    def admin_get_sweep_status(self) -> SweepStatusResponse:
        return self._run(self._async.admin_get_sweep_status())

    def admin_list_withdrawals(self, *, org_id: str | None = None) -> AdminWithdrawalListResponse:
        return self._run(self._async.admin_list_withdrawals(org_id=org_id))

    # ── Admin MCP ─────────────────────────────────────────────────────────────

    def admin_list_mcp_servers(self, org_id: str) -> list[McpServerResponse]:
        return self._run(self._async.admin_list_mcp_servers(org_id))

    # ── Admin Memory ──────────────────────────────────────────────────────────

    def admin_list_org_memories(self, org_id: str, *, limit: int = 50) -> AdminMemoryListResponse:
        return self._run(self._async.admin_list_org_memories(org_id, limit=limit))

    def admin_purge_org_memories(self, org_id: str) -> AdminMemoryPurgeResponse:
        return self._run(self._async.admin_purge_org_memories(org_id))

    # ── Admin Orgs ────────────────────────────────────────────────────────────

    def admin_get_spending_config(self, org_id: str) -> OrgSpendingConfigResponse:
        return self._run(self._async.admin_get_spending_config(org_id))

    def admin_update_spending_config(
        self, org_id: str, request: SpendingConfigUpdate
    ) -> OrgSpendingConfigResponse:
        return self._run(self._async.admin_update_spending_config(org_id, request))

    # ── Admin Pricing ─────────────────────────────────────────────────────────

    def admin_upsert_tool_pricing(
        self, request: ToolPricingOverrideRequest
    ) -> ToolPricingOverrideResponse:
        return self._run(self._async.admin_upsert_tool_pricing(request))

    def admin_delete_tool_pricing(self, tool_name: str) -> ToolPricingDeleteResponse:
        return self._run(self._async.admin_delete_tool_pricing(tool_name))

    # ── Admin Tools ───────────────────────────────────────────────────────────

    def admin_list_tools(self, org_id: str) -> list[OrgTool]:
        return self._run(self._async.admin_list_tools(org_id))

    # ── Admin Usage ───────────────────────────────────────────────────────────

    def admin_get_usage_org(
        self,
        org_id: str,
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> UsageSummary:
        return self._run(self._async.admin_get_usage_org(org_id, start=start, end=end))

    def admin_get_usage_user(
        self,
        user_id: str,
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> UsageSummary:
        return self._run(self._async.admin_get_usage_user(user_id, start=start, end=end))

    # ── Admin Telemetry ───────────────────────────────────────────────────────

    def admin_get_telemetry_completeness(self, *, days: int = 7) -> TelemetryCompletenessResponse:
        return self._run(self._async.admin_get_telemetry_completeness(days=days))
