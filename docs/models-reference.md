# Models Reference

All request/response types are Pydantic v2 models exported from `teardrop`.
Use this table to find which model backs which client method.

| Model | Used by |
|---|---|
| `JwtPayloadBase`, `TokenResponse` | `get_me()`, `register()`, `refresh()` |
| `AgentRunRequest` | `run()` (internal) |
| `SSEEvent` | `run()` yields |
| `CreditBalance` / `BillingBalance` | `get_balance()` |
| `BillingPricingResponse`, `ToolPricing` | `get_pricing()` |
| `BillingHistoryEntry` | `get_billing_history()` |
| `Invoice` | `get_invoices()`, `get_invoice()` |
| `CreditHistoryEntry` | `get_credit_history()` |
| `StripeTopupRequest`, `StripeTopupResponse`, `StripeTopupStatusResponse` | `topup_stripe()`, `get_stripe_topup_status()` |
| `UsdcTopupRequirements`, `UsdcTopupRequest` | `get_usdc_topup_requirements()`, `topup_usdc()` |
| `UsageSummary` | `get_usage()` |
| `OrgLlmConfig`, `SetLlmConfigRequest`, `ProviderType`, `RoutingPreference` | LLM config CRUD |
| `CreateScheduleRequest`, `ScheduledRun`, `ScheduledRunResult`, `ScheduledRunsPage`, `UpdateScheduleRequest` | `client.schedules.*` |
| `CreateEventTriggerRequest`, `EventTrigger`, `EventTriggerWithSecret`, `UpdateEventTriggerRequest` | `client.event_triggers.*` |
| `ModelBenchmarksResponse`, `ModelInfo`, `ModelPricing`, `ModelRunBenchmarks` | `get_model_benchmarks()`, `get_org_model_benchmarks()` |
| `Wallet`, `LinkWalletRequest` | `get_wallets()`, `link_wallet()` |
| `AgentCard` | `get_agent_card()` |
| `OrgTool`, `CreateOrgToolRequest`, `UpdateOrgToolRequest` | tool CRUD |
| `OrgMcpServer`, `CreateMcpServerRequest`, `UpdateMcpServerRequest`, `DiscoverMcpToolsResponse`, `McpToolDefinition` | MCP CRUD |
| `MemoryEntry`, `StoreMemoryRequest` | memory CRUD |
| `MarketplaceTool`, `MarketplaceSubscription`, `AuthorConfig`, `EarningsEntry`, `WithdrawRequest` | marketplace |
| `AddTrustedAgentRequest`, `TrustedAgent` | A2A delegation |
| `AgentWallet` | agent wallets |
| `AdminCreateA2AAgentRequest`, `AdminCreateClientCredentialsRequest`, `AdminCreateOrgRequest`, `AdminCreateUserRequest`, `AdminTopupRequest`, `CompleteWithdrawalRequest`, `SpendingConfigUpdate`, `ToolPricingOverrideRequest` | `admin.*` client methods |
| `AdminMemoryItem`, `AdminMemoryListResponse`, `AdminMemoryPurgeResponse`, `AdminWithdrawalItem`, `AdminWithdrawalListResponse`, `SweepStatusItem`, `SweepStatusResponse` | admin responses |
| `AdminTopupResponse`, `PendingSettlementItem`, `PendingSettlementsResponse`, `RevenueSummaryResponse`, `SettlementBalanceResponse`, `SettlementRetryResponse` | admin billing responses |
| `AdminWithdrawalActionResponse`, `CompleteWithdrawalResponse`, `MarketplaceSweepResponse`, `WithdrawalResetResponse` | admin marketplace responses |
| `CreateClientCredentialsResponse`, `CreateOrgResponse`, `CreateUserResponse`, `OrgSpendingConfigResponse` | admin identity and spending responses |
| `ToolPricingDeleteResponse`, `ToolPricingOverrideResponse` | admin pricing responses |

Import any model directly:

```python
from teardrop import (
	AdminCreateOrgRequest,
	AsyncAdminTeardropClient,
	OrgLlmConfig,
	ModelBenchmarksResponse,
	BillingBalance,
)
```

---

**Related:** [README](../README.md) · [spec/openapi.json](../spec/openapi.json) (authoritative schema source)
