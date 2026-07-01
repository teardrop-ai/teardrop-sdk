"""Synchronous Teardrop client facade."""

from __future__ import annotations

from typing import Any

from teardrop.client._async import AsyncTeardropClient
from teardrop.client.event_triggers import _SyncEventTriggersModule
from teardrop.client.schedules import _SyncSchedulesModule
from teardrop.models import (
    AddTrustedAgentRequest,
    AgentCard,
    AgentTool,
    AgentWallet,
    AuthorConfig,
    BillingBalance,
    BillingHistoryEntry,
    BillingPricingResponse,
    CreateMcpServerRequest,
    CreateOrgToolRequest,
    CreditHistoryEntry,
    DiscoverMcpToolsResponse,
    EarningsEntry,
    JwtPayloadBase,
    LinkWalletRequest,
    MarketplaceSubscription,
    MemoryEntry,
    ModelBenchmarksResponse,
    OrgLlmConfig,
    OrgMcpServer,
    OrgTool,
    SSEEvent,
    StoreMemoryRequest,
    StripeTopupRequest,
    StripeTopupResponse,
    StripeTopupStatusResponse,
    TokenResponse,
    TrustedAgent,
    UpdateMcpServerRequest,
    UpdateOrgToolRequest,
    UsageSummary,
    UsdcTopupRequest,
    UsdcTopupRequirements,
    Wallet,
    WithdrawRequest,
)


class TeardropClient:
    """Synchronous wrapper around AsyncTeardropClient."""

    def __init__(self, *args: Any, **kwargs: Any):
        self._async = AsyncTeardropClient(*args, **kwargs)
        self.schedules = _SyncSchedulesModule(self)
        self.event_triggers = _SyncEventTriggersModule(self)
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

    def run_sync(self, message: str, **kwargs: Any) -> list[SSEEvent]:
        async def _collect() -> list[SSEEvent]:
            events = []
            async for event in self._async.run(message, **kwargs):
                events.append(event)
            return events

        self._ensure_portal()
        return self._portal.call(_collect)  # type: ignore[union-attr]

    def get_agent_tools(self) -> list[AgentTool]:
        return self._run(self._async.get_agent_tools())

    def get_siwe_nonce(self) -> dict[str, str]:
        return self._run(self._async.get_siwe_nonce())

    def authenticate_siwe(self, message: str, signature: str) -> str:
        return self._run(self._async.authenticate_siwe(message, signature))

    def get_me(self) -> JwtPayloadBase:
        return self._run(self._async.get_me())

    def register(self, **kwargs: Any) -> TokenResponse:
        return self._run(self._async.register(**kwargs))

    def register_invite(self, **kwargs: Any) -> TokenResponse:
        return self._run(self._async.register_invite(**kwargs))

    def refresh(self, refresh_token: str) -> TokenResponse:
        return self._run(self._async.refresh(refresh_token))

    def logout(self, refresh_token: str) -> None:
        return self._run(self._async.logout(refresh_token))

    def verify_email(self, token: str) -> dict[str, Any]:
        return self._run(self._async.verify_email(token))

    def resend_verification(self, email: str) -> dict[str, Any]:
        return self._run(self._async.resend_verification(email))

    def invite(self, **kwargs: Any) -> dict[str, Any]:
        return self._run(self._async.invite(**kwargs))

    def get_balance(self) -> BillingBalance:
        return self._run(self._async.get_balance())

    def get_pricing(self) -> BillingPricingResponse:
        return self._run(self._async.get_pricing())

    def get_billing_history(self, *, limit: int = 20) -> list[BillingHistoryEntry]:
        return self._run(self._async.get_billing_history(limit=limit))

    def get_invoices(self, *, limit: int = 20) -> list[Any]:
        return self._run(self._async.get_invoices(limit=limit))

    def get_invoice(self, run_id: str):
        return self._run(self._async.get_invoice(run_id))

    def get_credit_history(
        self, *, limit: int = 20, operation: str | None = None
    ) -> list[CreditHistoryEntry]:
        return self._run(self._async.get_credit_history(limit=limit, operation=operation))

    def topup_stripe(self, request: StripeTopupRequest) -> StripeTopupResponse:
        return self._run(self._async.topup_stripe(request))

    def get_stripe_topup_status(self, session_id: str) -> StripeTopupStatusResponse:
        return self._run(self._async.get_stripe_topup_status(session_id))

    def get_usdc_topup_requirements(self, amount_usdc: int) -> UsdcTopupRequirements:
        return self._run(self._async.get_usdc_topup_requirements(amount_usdc))

    def topup_usdc(self, request: UsdcTopupRequest) -> dict[str, Any]:
        return self._run(self._async.topup_usdc(request))

    def get_usage(self, **kwargs: Any) -> UsageSummary:
        return self._run(self._async.get_usage(**kwargs))

    def link_wallet(self, request: LinkWalletRequest) -> Wallet:
        return self._run(self._async.link_wallet(request))

    def get_wallets(self) -> list[Wallet]:
        return self._run(self._async.get_wallets())

    def delete_wallet(self, wallet_id: str) -> None:
        return self._run(self._async.delete_wallet(wallet_id))

    def get_agent_card(self) -> AgentCard:
        return self._run(self._async.get_agent_card())

    def create_tool(self, request: CreateOrgToolRequest) -> OrgTool:
        return self._run(self._async.create_tool(request))

    def list_tools(self) -> list[OrgTool]:
        return self._run(self._async.list_tools())

    def get_tool(self, tool_id: str) -> OrgTool:
        return self._run(self._async.get_tool(tool_id))

    def update_tool(self, tool_id: str, request: UpdateOrgToolRequest) -> OrgTool:
        return self._run(self._async.update_tool(tool_id, request))

    def delete_tool(self, tool_id: str) -> None:
        return self._run(self._async.delete_tool(tool_id))

    def create_mcp_server(self, request: CreateMcpServerRequest) -> OrgMcpServer:
        return self._run(self._async.create_mcp_server(request))

    def list_mcp_servers(self) -> list[OrgMcpServer]:
        return self._run(self._async.list_mcp_servers())

    def get_mcp_server(self, server_id: str) -> OrgMcpServer:
        return self._run(self._async.get_mcp_server(server_id))

    def update_mcp_server(self, server_id: str, request: UpdateMcpServerRequest) -> OrgMcpServer:
        return self._run(self._async.update_mcp_server(server_id, request))

    def delete_mcp_server(self, server_id: str) -> None:
        return self._run(self._async.delete_mcp_server(server_id))

    def discover_mcp_server_tools(self, server_id: str) -> DiscoverMcpToolsResponse:
        return self._run(self._async.discover_mcp_server_tools(server_id))

    def list_memories(self, *, limit: int = 50) -> list[MemoryEntry]:
        return self._run(self._async.list_memories(limit=limit))

    def create_memory(self, request: StoreMemoryRequest) -> MemoryEntry:
        return self._run(self._async.create_memory(request))

    def delete_memory(self, memory_id: str) -> None:
        return self._run(self._async.delete_memory(memory_id))

    def get_marketplace_catalog(self, **kwargs: Any) -> dict[str, Any]:
        return self._run(self._async.get_marketplace_catalog(**kwargs))

    def set_author_config(self, settlement_wallet: str) -> AuthorConfig:
        return self._run(self._async.set_author_config(settlement_wallet))

    def get_author_config(self) -> AuthorConfig:
        return self._run(self._async.get_author_config())

    def get_marketplace_balance(self) -> dict[str, Any]:
        return self._run(self._async.get_marketplace_balance())

    def get_earnings(self, **kwargs: Any) -> list[EarningsEntry]:
        return self._run(self._async.get_earnings(**kwargs))

    def withdraw(self, request: WithdrawRequest) -> dict[str, Any]:
        return self._run(self._async.withdraw(request))

    def get_withdrawals(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self._run(self._async.get_withdrawals(**kwargs))

    def subscribe(self, qualified_tool_name: str) -> MarketplaceSubscription:
        return self._run(self._async.subscribe(qualified_tool_name))

    def get_subscriptions(self) -> list[MarketplaceSubscription]:
        return self._run(self._async.get_subscriptions())

    def unsubscribe(self, subscription_id: str) -> None:
        return self._run(self._async.unsubscribe(subscription_id))

    def get_llm_config(self) -> OrgLlmConfig:
        return self._run(self._async.get_llm_config())

    def set_llm_config(self, **kwargs: Any) -> OrgLlmConfig:
        return self._run(self._async.set_llm_config(**kwargs))

    def delete_llm_config(self) -> dict[str, Any]:
        return self._run(self._async.delete_llm_config())

    def get_model_benchmarks(self) -> ModelBenchmarksResponse:
        return self._run(self._async.get_model_benchmarks())

    def get_org_model_benchmarks(self) -> ModelBenchmarksResponse:
        return self._run(self._async.get_org_model_benchmarks())

    def list_supported_providers(self) -> list[str]:
        return self._async.list_supported_providers()

    def list_models_for_provider(self, provider: str) -> list[str]:
        return self._async.list_models_for_provider(provider)

    def add_trusted_agent(self, request: AddTrustedAgentRequest) -> TrustedAgent:
        return self._run(self._async.add_trusted_agent(request))

    def list_trusted_agents(self) -> list[TrustedAgent]:
        return self._run(self._async.list_trusted_agents())

    def remove_trusted_agent(self, agent_id: str) -> None:
        return self._run(self._async.remove_trusted_agent(agent_id))

    def get_delegations(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self._run(self._async.get_delegations(**kwargs))

    def provision_agent_wallet(self) -> AgentWallet:
        return self._run(self._async.provision_agent_wallet())

    def get_agent_wallet(self, **kwargs: Any) -> AgentWallet:
        return self._run(self._async.get_agent_wallet(**kwargs))

    def deactivate_agent_wallet(self) -> None:
        return self._run(self._async.deactivate_agent_wallet())

    def close(self) -> None:
        if self._portal is not None:
            self._portal.call(lambda: self._async.close())  # type: ignore[union-attr]
            self._portal_exit(None, None, None)  # type: ignore[misc]
            self._portal = None
            self._portal_exit = None

    @classmethod
    def from_agent_card(cls, base_url: str, **kwargs: Any):
        client = cls(base_url, **kwargs)
        client.get_agent_card()
        return client

    def __enter__(self):
        self._ensure_portal()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
