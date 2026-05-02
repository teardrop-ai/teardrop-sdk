# teardrop-sdk

Python SDK for the [Teardrop](https://github.com/teardrop-ai/teardrop) AI agent API.

## Requirements

- Python ≥ 3.11
- `httpx >= 0.28`, `pydantic >= 2.10`, `anyio >= 4.0`

## Install

```bash
pip install teardrop-sdk
```

## Quick Start

```python
import asyncio
from teardrop import AsyncTeardropClient

async def main():
    async with AsyncTeardropClient(
        "https://api.teardrop.dev",
        email="you@example.com",
        secret="your-password",
    ) as client:
        async for event in client.run("What is the ETH price on Base?"):
            if event.type == "TEXT_MESSAGE_CONTENT":
                print(event.data.get("delta", ""), end="", flush=True)
        print()

asyncio.run(main())
```

### Sync Usage

```python
from teardrop import TeardropClient

with TeardropClient(
    "https://api.teardrop.dev",
    email="you@example.com",
    secret="your-password",
) as client:
    for event in client.run_sync("What is 2 + 2?"):
        if event.type == "TEXT_MESSAGE_CONTENT":
            print(event.data.get("delta", ""), end="", flush=True)
    print()
```

`TeardropClient` is a thin synchronous wrapper around `AsyncTeardropClient`. Every async method on the async client has an identical sync counterpart, except `run()` → `run_sync()`.

---

## Authentication

Credentials are passed to the constructor. The `TokenManager` acquires a JWT automatically on the first request and refreshes it before expiry (30-minute window).

| Method | Constructor kwargs |
|---|---|
| Email + password | `email=..., secret=...` |
| Client credentials (M2M) | `client_id=..., client_secret=...` |
| Pre-authenticated static token | `token=...` |
| SIWE (sign-in with Ethereum) | Call `authenticate_siwe()` after construction (see below) |

### SIWE Login Flow

```python
async with AsyncTeardropClient("https://api.teardrop.dev") as client:
    # 1. Fetch a single-use nonce
    nonce_resp = await client.get_siwe_nonce()
    nonce = nonce_resp["nonce"]

    # 2. Build and sign an EIP-4361 message client-side (e.g. with siwe-py)
    #    Embed the nonce in the SIWE message body
    message = build_siwe_message(nonce=nonce, ...)
    signature = wallet.sign_message(message)

    # 3. Exchange for a JWT — stored automatically for subsequent calls
    token = await client.authenticate_siwe(message, signature)
```

### Email Registration

```python
tokens = await client.register(email="you@example.com", password="...")
# Verify email before first login
await client.verify_email(token=email_token)
```

### Token Refresh / Logout

```python
new_tokens = await client.refresh(refresh_token)
await client.logout(refresh_token)
```

### Inspect Identity

```python
me = await client.get_me()
# → JwtPayloadBase(sub=..., org_id=..., role="member", auth_method="email", ...)
```

---

## Marketplace

Discover, subscribe to, and monetize tools on the Teardrop marketplace. The marketplace is a curated catalogue of reusable agent tools built and published by the Teardrop community and core team. **For launch, the marketplace is Teardrop's primary product for tool distribution—use it to share tools with other orgs and earn revenue from usage.**

### Three Core Workflows

1. **Browsing** (public, no auth) — Discover tools in the marketplace catalogue
2. **Subscriptions** (auth required) — Subscribe to and use marketplace tools in your agent runs
3. **Publishing & Earnings** (auth required) — Publish your own tools and track revenue

### Browsing Tools (Public)

```python
# Browse full catalogue
catalog = await client.get_marketplace_catalog(limit=20)
tools: list[MarketplaceTool] = catalog["tools"]

# Filter by author org
catalog = await client.get_marketplace_catalog(org_slug="acme", limit=20)

# Sort and paginate
catalog = await client.get_marketplace_catalog(
    sort="price",          # "name" | "price" | "created_at"
    limit=50,
    cursor="next_page_token",  # from previous response
)

# Each tool includes metadata:
for tool in catalog["tools"]:
    print(f"{tool.org_slug}/{tool.name}: {tool.description}")
    print(f"  Price: ${tool.base_price_usdc / 1_000_000}")
    print(f"  Author: {tool.author_name}")
```

### Subscriptions & Integration

```python
# Subscribe to a tool
sub = await client.subscribe("acme/web_search")
# Tool is now available to your agent during runs

# List subscriptions
subs = await client.get_subscriptions()
# → list[MarketplaceSubscription]

# Unsubscribe
await client.unsubscribe(sub.id)
```

**Integration in Agent Runs**: After subscribing to a marketplace tool, the agent automatically discovers and can call it during `client.run()` without any additional configuration. See [Using Marketplace Tools in Agent Runs](#using-marketplace-tools-in-agent-runs) below.

### Publishing & Earnings

#### Author Setup

```python
# Configure payout wallet for earnings
config = await client.set_author_config(settlement_wallet="0xYourWalletAddress")
config = await client.get_author_config()
# → AuthorConfig(org_id=..., settlement_wallet="0x...")
```

#### Earnings & Revenue Tracking

```python
# Check total balance
balance = await client.get_marketplace_balance()
# → {"balance_usdc": 1500000, "pending_usdc": 250000, ...}

# Fetch earnings history (paginated)
entries: list[EarningsEntry] = await client.get_earnings(limit=50)
# Each entry tracks: tool_name, amount_usdc, author_share, platform_share, timestamp

# Filter earnings by tool
entries = await client.get_earnings(
    tool_name="web_search",
    limit=100,
    cursor="next_page",
)
```

#### Withdrawals

```python
from teardrop import WithdrawRequest

# Request payout
result = await client.withdraw(WithdrawRequest(amount_usdc=1_000_000))
# → {"status": "pending", "txn_id": "...", "settled_at": "..."}

# Withdrawal history
withdrawals = await client.get_withdrawals(limit=20)
for wd in withdrawals:
    print(f"{wd.amount_usdc} → settled {wd.settled_at}")
```

### Using Marketplace Tools in Agent Runs

Once subscribed to a marketplace tool, it becomes available to the agent and can be called during runs. The agent sees the tool's schema (inputs, outputs) and calls it like any built-in tool.

```python
# 1. Subscribe to a tool
await client.subscribe("acme/web_search")

# 2. Use it in agent runs (no explicit config needed)
async for event in client.run("Find the latest Bitcoin price using web_search"):
    if event.type == "TOOL_CALL_START":
        print(f"Agent called: {event.data['tool_name']}")
        # → "acme__web_search" (tool name is namespaced)
    if event.type == "TOOL_CALL_END":
        print(f"Result: {event.data['result']}")
```

#### Tool Naming

Marketplace tools are namespaced as `{org_slug}__{tool_name}` in tool call events.

```python
from teardrop import parse_marketplace_tool_name

parsed = parse_marketplace_tool_name("acme__web_search")
# → {"org_slug": "acme", "tool_name": "web_search"}
```

#### Error Handling

```python
from teardrop.exceptions import RateLimitError, PaymentRequiredError

try:
    async for event in client.run("Query subscribed tool"):
        ...
except PaymentRequiredError as e:
    # Insufficient balance for tool call
    print(f"Payment required: {e.requirements}")
    # Top up balance and retry
except RateLimitError as e:
    # Tool call rate limit hit
    await asyncio.sleep(e.retry_after)
```

### Marketplace vs. Custom Tools vs. MCP Servers

Teardrop offers three ways to extend agent capabilities. Choose based on your use case:

| Dimension | Marketplace Tools | Custom Webhook Tools | MCP Servers |
|---|---|---|---|
| **Scope** | Shared across orgs; discoverable catalogue | Org-private webhooks | External protocol servers |
| **Discovery** | Public browsing, subscriptions | Manual registration | Manual registration |
| **Monetization** | Built-in revenue sharing | Base pricing only | Not supported |
| **Maintenance** | Author owns; Teardrop supplies framework | You manage webhooks | You manage server |
| **Latency** | Routed through Teardrop | Direct webhook call | HTTP streaming |
| **Best for** | Sharing tools, generating revenue | Internal integrations, custom logic | Legacy systems, stdio tools |

**Decision Tree**:
- Publishing a tool for community use or revenue? → **Marketplace**
- Internal tool for your org's agent? → **Custom Webhook Tool**
- Integrating external services (Stripe, Slack, etc.)? → **MCP Server** or **Custom Webhook Tool**
- Need stdio-based tool protocol? → **MCP Server**

---

## Agent Runs

```python
async for event in client.run(
    "Summarise the top DeFi news today",
    thread_id="conv-abc123",          # optional; uuid generated if omitted
    model="claude-opus-4-5",          # optional LLM override
):
    print(event.type, event.data)
```

`run()` is an async generator that yields `SSEEvent` objects. The sync equivalent `run_sync()` blocks and returns `list[SSEEvent]`.

**Available Tools**: The agent automatically discovers and can call:
- Built-in Teardrop tools
- Marketplace tools you're subscribed to (see [Subscriptions & Integration](#subscriptions--integration))
- Custom webhook tools registered in your org (see [Custom Webhook Tools](#custom-webhook-tools))
- MCP servers you've registered (see [MCP Servers](#mcp-servers))

### Passing Context

```python
async for event in client.run(
    "Summarise the top DeFi news today",
    context={"user_timezone": "Europe/Berlin"},   # optional extra context dict
    thread_id="conv-abc123",
):
    ...
```

### x402 On-chain Payments

If the agent returns a `402 Payment Required` the SDK raises `PaymentRequiredError`. You can extract the requirements and the `payment_header` from the error to resolve the payment externally, then retry passing the x402 payment header:

```python
try:
    async for event in client.run("..."):
        ...
except PaymentRequiredError as e:
    # Resolve the payment using e.requirements and e.payment_header
    # Then retry with the resulting signature:
    async for event in client.run("...", payment_header="sig_...")
```

```python
async for event in client.run(
    "...",
    payment_header="...",   # X-Payment header value (retry after resolving 402)
    emit_ui=False           # Optional: disable SURFACE_UPDATE events (default: True)
):
    ...
```

```python
class SSEEvent:
    type: str            # see event type constants below
    data: dict[str, Any]
    id: str              # SSE stream ID (for resumption)
    retry: int | None    # retry interval in ms, if set by server
```

### Event Types

| `event.type` | `event.data` keys | Notes |
|---|---|---|
| `RUN_STARTED` | `run_id`, `thread_id` | First event of every run |
| `TEXT_MESSAGE_START` | `message_id` | Streaming text turn begins |
| `TEXT_MESSAGE_CONTENT` | `delta` | Streaming text chunk |
| `TEXT_MESSAGE_END` | `message_id` | Streaming text turn ends |
| `TOOL_CALL_START` | `tool_call_id`, `tool_name`, `args` | Agent is calling a tool |
| `TOOL_CALL_END` | `tool_call_id`, `result` | Tool returned |
| `SURFACE_UPDATE` | `surface`, `content` | UI surface payload |
| `USAGE_SUMMARY` | `tokens_in`, `tokens_out`, `tool_calls` | Per-run token usage |
| `BILLING_SETTLEMENT` | `run_id`, `cost_usdc` | Credit deducted |
| `ERROR` | `message`, `code` | Non-fatal error during run |
| `DONE` | *(empty)* | Stream complete |

### x402 On-chain Payments

If the agent returns a `402 Payment Required` the SDK raises `PaymentRequiredError`. You can extract the requirements and the `payment_header` from the error to resolve the payment externally, then retry passing the x402 payment header:

```python
try:
    async for event in client.run("..."):
        ...
except PaymentRequiredError as e:
    # Resolve the payment using e.requirements and e.payment_header
    # Then retry with the resulting signature:
    async for event in client.run("...", payment_header="sig_...")
```

---

## Error Handling

All exceptions inherit from `TeardropError`.

```python
from teardrop.exceptions import (
    TeardropError,
    AuthenticationError,    # 401
    PaymentRequiredError,   # 402  — .requirements dict attached
    ForbiddenError,         # 403
    NotFoundError,          # 404
    ConflictError,          # 409
    ValidationError,        # 422
    RateLimitError,         # 429  — .retry_after (seconds)
    GatewayError,           # 502 / 504
    APIError,               # all other non-2xx
)
```

```python
from teardrop.exceptions import RateLimitError, PaymentRequiredError
import asyncio

try:
    async for event in client.run("..."):
        ...
except RateLimitError as e:
    await asyncio.sleep(e.retry_after)
except PaymentRequiredError as e:
    print("x402 requirements:", e.requirements)
```

---

## Billing

### Balance

```python
balance = await client.get_balance()
# → BillingBalance(org_id=..., balance_usdc=5000, spending_limit_usdc=10000, is_paused=False)
```

USDC amounts are in atomic units (6 decimals). Use `format_usdc()` / `parse_usdc()` helpers:

```python
from teardrop import format_usdc, parse_usdc
print(format_usdc(5_000_000))  # → "5.000000"
print(parse_usdc("1.50"))      # → 1500000
```

### Pricing

```python
pricing = await client.get_pricing()   # no auth required
for tool in pricing.tools:
    print(tool.tool_name, tool.price_usdc)
```

### Billing History

```python
entries: list[BillingHistoryEntry] = await client.get_billing_history(limit=50)
```

### Invoices

```python
# Flat list
invoices: list[Invoice] = await client.get_invoices(limit=20)

# Single run invoice
invoice = await client.get_invoice(run_id)
# → Invoice(run_id=..., tokens_in=..., tokens_out=..., tool_calls=..., total_usdc=..., settled_at=...)
```

### Credit History

```python
entries: list[CreditHistoryEntry] = await client.get_credit_history(operation="topup")
```

### Stripe Top-up

```python
from teardrop import StripeTopupRequest

resp = await client.topup_stripe(StripeTopupRequest(
    amount_cents=1000,                             # $10.00 in cents
    return_url="https://app.example.com/billing",
))
# resp.client_secret — pass to Stripe.js to confirm payment
# resp.session_id   — use to poll status

# Poll for completion
status = await client.get_stripe_topup_status(resp.session_id)
# → StripeTopupStatusResponse(status="complete"|"open"|"expired", new_balance_fmt="$15.00")
```

### USDC Top-up (on-chain x402)

```python
from teardrop import UsdcTopupRequest

# Fetch payment requirements for a given amount
reqs = await client.get_usdc_topup_requirements(amount_usdc=5_000_000)
# → UsdcTopupRequirements(accepts=[{...}], x402Version=2)

result = await client.topup_usdc(UsdcTopupRequest(
    amount_usdc=5_000_000,
    payment_header="...",   # x402 payment header value
))
```

### Usage Summary

```python
summary = await client.get_usage(start="2026-04-01", end="2026-04-30")
# → UsageSummary(total_runs=..., total_tokens_in=..., total_tokens_out=...,
#                total_tool_calls=..., total_duration_ms=...)
```

---

## LLM Configuration

Customize which LLM provider and model the agent uses, enable bring-your-own-key (BYOK), or route to self-hosted endpoints. Configuration is org-scoped and persists across runs.

### Get Current Config

```python
config = await client.get_llm_config()
# → OrgLlmConfig(
#     org_id=..., provider="anthropic", model="claude-haiku-4-5-20251001",
#     has_api_key=False, api_base=None, max_tokens=4096, temperature=0.0,
#     routing_preference="default", is_byok=False, created_at=..., updated_at=...
#   )
```

Results are cached for 5 minutes.

### Set LLM Config

```python
from teardrop import SetLlmConfigRequest

config = await client.set_llm_config(
    provider="anthropic",                          # "anthropic" | "openai" | "google" | "openrouter"
    model="claude-sonnet-4-20250514",
    routing_preference="cost",                     # "default" | "cost" | "speed" | "quality"
    api_key=None,                                  # optional BYOK key (TLS-only, never logged)
    api_base=None,                                 # optional self-hosted endpoint (vLLM/Ollama)
    max_tokens=4096,                               # 1–200,000
    temperature=0.0,                               # 0.0–2.0
    timeout_seconds=120,
)
```

**Notes**:
- Pass `api_key=None` (or omit) to preserve an existing stored key.
- When `api_key` is provided, it is encrypted at rest and never returned (only `has_api_key: true` is visible).
- `api_base` is validated for SSRF; private IPs are rejected unless the backend explicitly allows them.
- `routing_preference="cost"` enables smart routing to find the cheapest model in a pool.
- Cache is invalidated on successful update.

### Delete LLM Config

```python
await client.delete_llm_config()
# → {"status": "deleted"}
```

Reverts the org to global default LLM config. Returns `404` if no config exists (safe to call idempotently).

### Supported Providers & Models

```python
providers = client.list_supported_providers()
# → ["anthropic", "openai", "google", "openrouter"]

models = client.list_models_for_provider("anthropic")
# → ["claude-haiku-4-5-20251001", "claude-sonnet-4-20250514"]

# Inspect the constant directly
from teardrop import MODELS_BY_PROVIDER
print(MODELS_BY_PROVIDER)
```

---

## Model Benchmarks

Browse model capabilities and operational metrics (latency, cost, throughput) across your org's usage.

### Public Model Catalogue

```python
benchmarks = await client.get_model_benchmarks()  # no auth required
# → ModelBenchmarksResponse(
#     models=[
#       ModelInfo(
#         provider="anthropic",
#         model="claude-haiku-4-5-20251001",
#         display_name="Claude Haiku 4.5",
#         context_window=200000,
#         supports_tools=True,
#         supports_streaming=True,
#         quality_tier=2,
#         pricing=ModelPricing(
#           tokens_in_cost_per_1k=0.08,
#           tokens_out_cost_per_1k=0.24,
#           tool_call_cost=0.0
#         ),
#         benchmarks=ModelRunBenchmarks(
#           total_runs_7d=1250,
#           avg_latency_ms=485.5,
#           p95_latency_ms=1200.0,
#           avg_cost_usdc_per_run=12.5,
#           avg_tokens_per_sec=45.2
#         )
#       ),
#       ...
#     ],
#     updated_at="2026-04-16T12:00:00Z"
#   )
```

**Notes**:
- Results are cached for 10 minutes.
- `benchmarks` field is `None` for models with < 10 runs in the 7-day window.
- `pricing` is always present (sourced from current pricing rules).

### Org-Scoped Benchmarks

```python
org_benchmarks = await client.get_org_model_benchmarks()  # auth required
```

Same response structure as public benchmarks, but filtered to your org's usage only. **Not cached** — always fresh query. Returns empty model list if org has no usage data.

### Use Case: Choosing Models

```python
benchmarks = await client.get_model_benchmarks()

# Find cheapest
cheapest = min(
    (m for m in benchmarks.models if m.benchmarks),
    key=lambda m: m.pricing.tokens_in_cost_per_1k + m.pricing.tokens_out_cost_per_1k
)

# Find fastest
fastest = min(
    (m for m in benchmarks.models if m.benchmarks),
    key=lambda m: m.benchmarks.avg_latency_ms
)

print(f"Cheapest: {cheapest.model}")
print(f"Fastest: {fastest.model}")

# Configure agent to use cheapest
await client.set_llm_config(
    provider=cheapest.provider,
    model=cheapest.model,
    routing_preference="cost",
)
```

---

## Wallets

Link Ethereum wallets to a user account for USDC payments and SIWE authentication.

```python
from teardrop import LinkWalletRequest

wallet = await client.link_wallet(LinkWalletRequest(
    siwe_message="...",
    siwe_signature="...",
))

wallets: list[Wallet] = await client.get_wallets()

await client.delete_wallet(wallet.id)
```

---

## Custom Webhook Tools

Register custom webhook-backed tools for your org that the agent can call during runs. These are private to your organization and not shared on the marketplace (unless explicitly published). For comparison with marketplace tools and MCP servers, see [Marketplace vs. Custom Tools vs. MCP Servers](#marketplace-vs-custom-tools-vs-mcp-servers) above.

```python
from teardrop import CreateOrgToolRequest, UpdateOrgToolRequest

# Register
tool = await client.create_tool(CreateOrgToolRequest(
    name="send_email",                      # lowercase, a-z0-9_
    description="Send an email via Sendgrid",
    input_schema={                          # JSON Schema object
        "type": "object",
        "properties": {
            "to": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
        },
        "required": ["to", "subject", "body"],
    },
    webhook_url="https://hooks.example.com/email",
    webhook_method="POST",                  # optional, default POST
    auth_header_name="X-Webhook-Secret",   # optional auth header
    auth_header_value="whsec_...",
    timeout_seconds=10,
))

tools: list[OrgTool] = await client.list_tools()
tool = await client.get_tool(tool.id)

# Partial update — only provided fields are sent
updated = await client.update_tool(tool.id, UpdateOrgToolRequest(
    description="Send email via AWS SES",
    is_active=False,
))

await client.delete_tool(tool.id)
```

---

## MCP Servers

Register external MCP (Model Context Protocol) servers. The agent auto-discovers their tools at run time and namespaces them as `{server_name}__{tool_name}`.

```python
from teardrop import CreateMcpServerRequest, UpdateMcpServerRequest, parse_mcp_tool_name

# Register
server = await client.create_mcp_server(CreateMcpServerRequest(
    name="stripe",                              # becomes tool prefix
    url="https://your-stripe-mcp.example.com/sse",
    auth_type="bearer",                         # "none" | "bearer" | "header"
    auth_token="sk-...",                        # write-only; never returned
    timeout_seconds=15,
))

servers: list[OrgMcpServer] = await client.list_mcp_servers()
server = await client.get_mcp_server(server.id)

# Partial update
await client.update_mcp_server(server.id, UpdateMcpServerRequest(
    auth_token="sk-new-...",
    timeout_seconds=30,
))

# Live probe — bypasses agent TTL cache, does not mutate state
discovery = await client.discover_mcp_server_tools(server.id)
for tool in discovery.tools:
    print(tool.name, tool.description)

await client.delete_mcp_server(server.id)
```

### MCP Tool Names in Events

```python
async for event in client.run("Issue a refund for ch_abc123"):
    if event.type == "TOOL_CALL_START":
        parsed = parse_mcp_tool_name(event.data["tool_name"])
        if parsed["is_mcp"]:
            print(f"MCP → {parsed['server']}.{parsed['tool']}")
```

```python
parse_mcp_tool_name("stripe__create_refund")
# → {"is_mcp": True, "server": "stripe", "tool": "create_refund"}

parse_mcp_tool_name("web_search")
# → {"is_mcp": False}
```

### MCP Behavioural Notes

| Constraint | Detail |
|---|---|
| Quota | 5 active servers per org by default; `422` on breach |
| Cache lag | New/updated servers are live within ~5 min (TTL 300 s); `/discover` bypasses cache |
| Auth write-only | `auth_token` is write-only; only `has_auth: bool` is returned |
| Transport | Streamable HTTP only — stdio MCP servers are not supported |
| SSRF | Server-side URL validation blocks private IPs and localhost |

---

## Memory

Store and retrieve persistent memory entries scoped to the org. The agent can read these during runs.

```python
from teardrop import StoreMemoryRequest

entry = await client.create_memory(StoreMemoryRequest(
    content="User prefers responses in Spanish.",  # 1–500 characters
))

entries: list[MemoryEntry] = await client.list_memories(limit=50)

await client.delete_memory(entry.id)
```

---

## A2A Delegation

Allow other organisations' agents to call your agent on behalf of their users.

```python
from teardrop import AddTrustedAgentRequest

# Grant delegation rights to an org
agent = await client.add_trusted_agent(AddTrustedAgentRequest(
    org_id="org-partner-abc",
    permissions=["run"],
))

agents: list[TrustedAgent] = await client.list_trusted_agents()

await client.remove_trusted_agent(agent.id)

# View delegation event history
delegations = await client.get_delegations(limit=20)
```

---

## Agent Wallets

Provision a CDP smart wallet for the org's agent, enabling it to sign transactions autonomously.

```python
wallet = await client.provision_agent_wallet()
# \u2192 AgentWallet(id=..., address=\"0x...\", network=\"base\", status=\"active\")

# Fetch with live on-chain balance
wallet = await client.get_agent_wallet(include_balance=True)

# Deactivate (admin only)
await client.deactivate_agent_wallet()
```

---

## Agent Card

Fetch the A2A agent card from `/.well-known/agent-card.json`. Result is cached for 5 minutes.

```python
card = await client.get_agent_card()
# → AgentCard(name=..., description=..., url=..., skills=[...])

# Bypass cache
card = await client.get_agent_card(force_refresh=True)
```

Alternatively, create a client and pre-warm the cache atomically:

```python
client = await AsyncTeardropClient.from_agent_card("https://api.teardrop.dev", email="...", secret="...")
```

---

## Models Reference

All request/response types are Pydantic v2 models exported from `teardrop`.

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
| `ModelBenchmarksResponse`, `ModelInfo`, `ModelPricing`, `ModelRunBenchmarks` | `get_model_benchmarks()`, `get_org_model_benchmarks()` |
| `Wallet`, `LinkWalletRequest` | `get_wallets()`, `link_wallet()` |
| `AgentCard` | `get_agent_card()` |
| `OrgTool`, `CreateOrgToolRequest`, `UpdateOrgToolRequest` | tool CRUD |
| `OrgMcpServer`, `CreateMcpServerRequest`, `UpdateMcpServerRequest`, `DiscoverMcpToolsResponse`, `McpToolDefinition` | MCP CRUD |
| `MemoryEntry`, `StoreMemoryRequest` | memory CRUD |
| `MarketplaceTool`, `MarketplaceSubscription`, `AuthorConfig`, `EarningsEntry`, `WithdrawRequest` | marketplace |
| `AddTrustedAgentRequest`, `TrustedAgent` | A2A delegation |
| `AgentWallet` | agent wallets |

Import any model directly:

```python
from teardrop import OrgLlmConfig, ModelBenchmarksResponse, BillingBalance
```

---

## Development

```bash
# install dev deps
pip install -e ".[dev]"

# run tests
pytest

# run tests with coverage
pytest --cov=teardrop --cov-report=term-missing
```

### Integration Tests

Integration tests make real HTTP requests against the Teardrop API. Set the following environment variables to enable them:

```bash
export TEARDROP_TEST_URL="https://api.teardrop.dev"
export TEARDROP_TEST_EMAIL="you@example.com"
export TEARDROP_TEST_SECRET="your-password"

pytest tests/integration/ -v
```

Without those variables set, all integration tests are skipped automatically.
