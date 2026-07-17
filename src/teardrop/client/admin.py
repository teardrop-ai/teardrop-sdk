"""Admin-only client methods covering all /admin/* routes from the spec."""

from __future__ import annotations

from typing import Any

from teardrop.client._core import _quote_path_segment
from teardrop.models import (
    A2AAgentDeletedResponse,
    A2AAgentListItem,
    A2AAgentResponse,
    AdminCreateA2AAgentRequest,
    AdminCreateClientCredentialsRequest,
    AdminCreateOrgRequest,
    AdminCreateUserRequest,
    AdminTopupRequest,
    AdminTopupResponse,
    CompleteWithdrawalRequest,
    CreateClientCredentialsResponse,
    CreateOrgResponse,
    CreateUserResponse,
    PendingSettlementsResponse,
    RevenueSummaryResponse,
    SettlementRetryResponse,
    SpendingConfigUpdate,
    ToolPricingDeleteResponse,
    ToolPricingOverrideRequest,
    ToolPricingOverrideResponse,
    UsageSummary,
)
from teardrop.models.billing import SettlementBalanceResponse
from teardrop.models.marketplace import (
    AdminWithdrawalActionResponse,
    AdminWithdrawalListResponse,
    CompleteWithdrawalResponse,
    MarketplaceSweepResponse,
    SweepStatusResponse,
    WithdrawalResetResponse,
)
from teardrop.models.mcp import McpServerResponse
from teardrop.models.memory import (
    AdminMemoryListResponse,
    AdminMemoryPurgeResponse,
)
from teardrop.models.org import OrgSpendingConfigResponse
from teardrop.models.tools import OrgTool


class _AdminMixin:
    # ── Admin A2A ─────────────────────────────────────────────────────────────

    async def admin_add_a2a_agent(self, request: AdminCreateA2AAgentRequest) -> A2AAgentResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/admin/a2a/agents",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return A2AAgentResponse.model_validate(resp.json())

    async def admin_delete_a2a_agent(self, agent_id: str) -> A2AAgentDeletedResponse:
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/admin/a2a/agents/{_quote_path_segment(agent_id)}",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return A2AAgentDeletedResponse.model_validate(resp.json())

    async def admin_list_a2a_agents(self, org_id: str) -> list[A2AAgentListItem]:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/admin/a2a/agents/{_quote_path_segment(org_id)}",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        data = resp.json()
        return [A2AAgentListItem.model_validate(item) for item in data]

    # ── Admin Billing ─────────────────────────────────────────────────────────

    async def admin_get_pending_settlements(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> PendingSettlementsResponse:
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        if status is not None:
            params["status"] = status
        resp = await http.get(
            f"{self._base_url}/admin/billing/pending",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        return PendingSettlementsResponse.model_validate(resp.json())

    async def admin_retry_settlement(self, settlement_id: str) -> SettlementRetryResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/admin/billing/pending/{_quote_path_segment(settlement_id)}/retry",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return SettlementRetryResponse.model_validate(resp.json())

    async def admin_get_revenue(
        self,
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> RevenueSummaryResponse:
        http = await self._get_http()
        params: dict[str, Any] = {}
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
        resp = await http.get(
            f"{self._base_url}/admin/billing/revenue",
            headers=await self._headers(),
            params=params or None,
        )
        self._raise_for_status(resp)
        return RevenueSummaryResponse.model_validate(resp.json())

    async def admin_topup_credits(self, request: AdminTopupRequest) -> AdminTopupResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/admin/credits/topup",
            json=request.model_dump(),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return AdminTopupResponse.model_validate(resp.json())

    # ── Admin Identity ────────────────────────────────────────────────────────

    async def admin_create_client_credentials(
        self, request: AdminCreateClientCredentialsRequest
    ) -> CreateClientCredentialsResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/admin/client-credentials",
            json=request.model_dump(),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return CreateClientCredentialsResponse.model_validate(resp.json())

    async def admin_create_org(self, request: AdminCreateOrgRequest) -> CreateOrgResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/admin/orgs",
            json=request.model_dump(),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return CreateOrgResponse.model_validate(resp.json())

    async def admin_create_user(self, request: AdminCreateUserRequest) -> CreateUserResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/admin/users",
            json=request.model_dump(),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return CreateUserResponse.model_validate(resp.json())

    # ── Admin Marketplace ─────────────────────────────────────────────────────

    async def admin_complete_withdrawal(
        self, withdrawal_id: str, request: CompleteWithdrawalRequest
    ) -> CompleteWithdrawalResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/admin/marketplace/complete-withdrawal/{_quote_path_segment(withdrawal_id)}",
            json=request.model_dump(),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return CompleteWithdrawalResponse.model_validate(resp.json())

    async def admin_process_withdrawal(self, withdrawal_id: str) -> AdminWithdrawalActionResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/admin/marketplace/process-withdrawal/{_quote_path_segment(withdrawal_id)}",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return AdminWithdrawalActionResponse.model_validate(resp.json())

    async def admin_reset_withdrawal(self, withdrawal_id: str) -> WithdrawalResetResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/admin/marketplace/reset-withdrawal/{_quote_path_segment(withdrawal_id)}",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return WithdrawalResetResponse.model_validate(resp.json())

    async def admin_get_settlement_balance(self) -> SettlementBalanceResponse:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/admin/marketplace/settlement-balance",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return SettlementBalanceResponse.model_validate(resp.json())

    async def admin_sweep_marketplace(self) -> MarketplaceSweepResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/admin/marketplace/sweep",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return MarketplaceSweepResponse.model_validate(resp.json())

    async def admin_sweep_retry_withdrawal(self, withdrawal_id: str) -> WithdrawalResetResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/admin/marketplace/sweep-retry/{_quote_path_segment(withdrawal_id)}",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return WithdrawalResetResponse.model_validate(resp.json())

    async def admin_get_sweep_status(self) -> SweepStatusResponse:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/admin/marketplace/sweep-status",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return SweepStatusResponse.model_validate(resp.json())

    async def admin_list_withdrawals(
        self, *, org_id: str | None = None
    ) -> AdminWithdrawalListResponse:
        http = await self._get_http()
        params: dict[str, Any] = {}
        if org_id is not None:
            params["org_id"] = org_id
        resp = await http.get(
            f"{self._base_url}/admin/marketplace/withdrawals",
            headers=await self._headers(),
            params=params or None,
        )
        self._raise_for_status(resp)
        return AdminWithdrawalListResponse.model_validate(resp.json())

    # ── Admin MCP ─────────────────────────────────────────────────────────────

    async def admin_list_mcp_servers(self, org_id: str) -> list[McpServerResponse]:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/admin/mcp/servers/{_quote_path_segment(org_id)}",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        data = resp.json()
        return [McpServerResponse.model_validate(item) for item in data]

    # ── Admin Memory ──────────────────────────────────────────────────────────

    async def admin_list_org_memories(
        self, org_id: str, *, limit: int = 50
    ) -> AdminMemoryListResponse:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/admin/memories/org/{_quote_path_segment(org_id)}",
            headers=await self._headers(),
            params={"limit": limit},
        )
        self._raise_for_status(resp)
        return AdminMemoryListResponse.model_validate(resp.json())

    async def admin_purge_org_memories(self, org_id: str) -> AdminMemoryPurgeResponse:
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/admin/memories/org/{_quote_path_segment(org_id)}",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return AdminMemoryPurgeResponse.model_validate(resp.json())

    # ── Admin Orgs ────────────────────────────────────────────────────────────

    async def admin_get_spending_config(self, org_id: str) -> OrgSpendingConfigResponse:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/admin/orgs/{_quote_path_segment(org_id)}/spending",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return OrgSpendingConfigResponse.model_validate(resp.json())

    async def admin_update_spending_config(
        self, org_id: str, request: SpendingConfigUpdate
    ) -> OrgSpendingConfigResponse:
        http = await self._get_http()
        resp = await http.patch(
            f"{self._base_url}/admin/orgs/{_quote_path_segment(org_id)}/spending",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return OrgSpendingConfigResponse.model_validate(resp.json())

    # ── Admin Pricing ─────────────────────────────────────────────────────────

    async def admin_upsert_tool_pricing(
        self, request: ToolPricingOverrideRequest
    ) -> ToolPricingOverrideResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/admin/pricing/tools",
            json=request.model_dump(),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return ToolPricingOverrideResponse.model_validate(resp.json())

    async def admin_delete_tool_pricing(self, tool_name: str) -> ToolPricingDeleteResponse:
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/admin/pricing/tools/{_quote_path_segment(tool_name)}",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return ToolPricingDeleteResponse.model_validate(resp.json())

    # ── Admin Tools ───────────────────────────────────────────────────────────

    async def admin_list_tools(self, org_id: str) -> list[OrgTool]:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/admin/tools/{_quote_path_segment(org_id)}",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        data = resp.json()
        return [OrgTool.model_validate(item) for item in data]

    # ── Admin Usage ───────────────────────────────────────────────────────────

    async def admin_get_usage_org(
        self,
        org_id: str,
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> UsageSummary:
        http = await self._get_http()
        params: dict[str, Any] = {}
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
        resp = await http.get(
            f"{self._base_url}/admin/usage/org/{_quote_path_segment(org_id)}",
            headers=await self._headers(),
            params=params or None,
        )
        self._raise_for_status(resp)
        return UsageSummary.model_validate(resp.json())

    async def admin_get_usage_user(
        self,
        user_id: str,
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> UsageSummary:
        http = await self._get_http()
        params: dict[str, Any] = {}
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
        resp = await http.get(
            f"{self._base_url}/admin/usage/{_quote_path_segment(user_id)}",
            headers=await self._headers(),
            params=params or None,
        )
        self._raise_for_status(resp)
        return UsageSummary.model_validate(resp.json())
