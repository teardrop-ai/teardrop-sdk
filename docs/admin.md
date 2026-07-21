# Admin Client

The Teardrop SDK ships a dedicated admin surface for privileged operations:

```python
from teardrop import AsyncAdminTeardropClient

async with AsyncAdminTeardropClient(
    "https://api.teardrop.dev",
    token="admin-token-here",
) as admin:
    balance = await admin.admin_get_settlement_balance()
    print(balance.balance_usdc)
```

## Sync Usage

```python
from teardrop import AdminTeardropClient

with AdminTeardropClient(
    "https://api.teardrop.dev",
    token="admin-token-here",
) as admin:
    balance = admin.admin_get_settlement_balance()
    print(balance.balance_usdc)
```

## Available Operations

| Domain | Method | Spec Route |
|---|---|---|
| A2A | `admin_add_a2a_agent(req)` | `POST /admin/a2a/agents` |
| A2A | `admin_delete_a2a_agent(agent_id)` | `DELETE /admin/a2a/agents/{agent_id}` |
| A2A | `admin_list_a2a_agents(org_id)` | `GET /admin/a2a/agents/{org_id}` |
| Billing | `admin_get_pending_settlements(status, limit)` | `GET /admin/billing/pending` |
| Billing | `admin_retry_settlement(settlement_id)` | `POST /admin/billing/pending/{settlement_id}/retry` |
| Billing | `admin_get_revenue(start, end)` | `GET /admin/billing/revenue` |
| Billing | `admin_topup_credits(req)` | `POST /admin/credits/topup` |
| Identity | `admin_create_client_credentials(req)` | `POST /admin/client-credentials` |
| Identity | `admin_create_org(req)` | `POST /admin/orgs` |
| Identity | `admin_create_user(req)` | `POST /admin/users` |
| Marketplace | `admin_complete_withdrawal(id, req)` | `POST /admin/marketplace/complete-withdrawal/{id}` |
| Marketplace | `admin_process_withdrawal(id)` | `POST /admin/marketplace/process-withdrawal/{id}` |
| Marketplace | `admin_reset_withdrawal(id)` | `POST /admin/marketplace/reset-withdrawal/{id}` |
| Marketplace | `admin_get_settlement_balance()` | `GET /admin/marketplace/settlement-balance` |
| Marketplace | `admin_sweep_marketplace()` | `POST /admin/marketplace/sweep` |
| Marketplace | `admin_sweep_retry_withdrawal(id)` | `POST /admin/marketplace/sweep-retry/{id}` |
| Marketplace | `admin_get_sweep_status()` | `GET /admin/marketplace/sweep-status` |
| Marketplace | `admin_list_withdrawals(org_id)` | `GET /admin/marketplace/withdrawals` |
| MCP | `admin_list_mcp_servers(org_id)` | `GET /admin/mcp/servers/{org_id}` |
| Memory | `admin_list_org_memories(org_id, limit)` | `GET /admin/memories/org/{org_id}` |
| Memory | `admin_purge_org_memories(org_id)` | `DELETE /admin/memories/org/{org_id}` |
| Orgs | `admin_get_spending_config(org_id)` | `GET /admin/orgs/{org_id}/spending` |
| Orgs | `admin_update_spending_config(org_id, req)` | `PATCH /admin/orgs/{org_id}/spending` |
| Pricing | `admin_upsert_tool_pricing(req)` | `POST /admin/pricing/tools` |
| Pricing | `admin_delete_tool_pricing(tool_name)` | `DELETE /admin/pricing/tools/{tool_name}` |
| Tools | `admin_list_tools(org_id)` | `GET /admin/tools/{org_id}` |
| Usage | `admin_get_usage_org(org_id, start, end)` | `GET /admin/usage/org/{org_id}` |
| Usage | `admin_get_usage_user(user_id, start, end)` | `GET /admin/usage/{user_id}` |
| Telemetry | `admin_get_telemetry_completeness(days)` | `GET /admin/telemetry/completeness` |

## Security Boundary

Admin endpoints are intentionally separated from the standard `AsyncTeardropClient` / `TeardropClient` surfaces. This makes the privileged surface explicit and reduces accidental misuse. However, admin clients are **not** an authorization boundary — the backend must reject non-admin tokens. The SDK simply organizes the API surface by privilege level.

Use an admin client for new code. The regular client methods `get_admin_usage_org()` and
`get_admin_usage_user()` remain as deprecated compatibility shims for one release and emit
`DeprecationWarning`; migrate them to `admin_get_usage_org()` and `admin_get_usage_user()` on
`AsyncAdminTeardropClient` or `AdminTeardropClient`.

Admin credentials and client secrets are sensitive. Keep them in a secret manager, never log
them, and close the client when finished. The SDK does not persist tokens or enforce backend
authorization.

## Models

All admin request models are in `teardrop.models.admin`:

- `AdminCreateA2AAgentRequest`
- `AdminCreateClientCredentialsRequest`
- `AdminCreateOrgRequest`
- `AdminCreateUserRequest`
- `AdminTopupRequest`
- `CompleteWithdrawalRequest`
- `SpendingConfigUpdate`
- `ToolPricingOverrideRequest`

Response models are exported from their domain modules (`teardrop.models.billing`, `teardrop.models.marketplace`, etc.) and re-exported from `teardrop.models`.

---

**Related:** [README](../README.md) · [spec/openapi.json](../spec/openapi.json) (authoritative schema source) · [Models Reference](models-reference.md)
