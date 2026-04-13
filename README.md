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
    message = build_siwe_message(nonce=nonce, ...)
    signature = wallet.sign_message(message)

    # 3. Exchange for a JWT — stored automatically for subsequent calls
    token = await client.authenticate_siwe(message, signature, nonce)
```

### Inspect Identity

```python
me = await client.get_me()
# → JwtPayloadBase(sub=..., org_id=..., role="member", auth_method="email", ...)
```

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

### SSEEvent

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
| `TEXT_MESSAGE_CONTENT` | `delta` | Streaming text chunk |
| `TOOL_CALL_START` | `tool_call_id`, `tool_name`, `args` | Agent is calling a tool |
| `TOOL_CALL_END` | `tool_call_id`, `result` | Tool returned |
| `SURFACE_UPDATE` | `surface`, `content` | UI surface payload |
| `USAGE_SUMMARY` | `tokens_in`, `tokens_out`, `tool_calls` | Per-run token usage |
| `BILLING_SETTLEMENT` | `run_id`, `cost_usdc` | Credit deducted |
| `ERROR` | `message`, `code` | Non-fatal error during run |
| `DONE` | *(empty)* | Stream complete |

### x402 Payments

If the agent returns a `402 Payment Required` the SDK raises `PaymentRequiredError`. Resolve the payment externally and retry with:

```python
async for event in client.run(
    prompt,
    x402_payment_header="...",   # value from 402 response
    payment_signature="...",     # EIP-3009 signature
):
    ...
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
# → BillingBalance(org_id=..., balance_usdc=5000, reserved_usdc=200, available_usdc=4800)
```

USDC amounts are in atomic units (micro-USDC, 6 decimals). Divide by `1_000_000` for human-readable USDC.

### Pricing

```python
pricing = await client.get_pricing()   # no auth required
for tool in pricing.tools:
    print(tool.tool_name, tool.price_usdc)
```

### Billing History

```python
page = await client.get_billing_history(limit=50)
entries: list[BillingHistoryEntry] = page["items"]
cursor = page.get("next_cursor")        # pass to next call to paginate
```

### Invoices

```python
# Paginated list
page = await client.get_invoices(limit=20, cursor=cursor)

# Single run invoice
invoice = await client.get_invoice(run_id)
# → Invoice(run_id=..., tokens_in=..., tokens_out=..., tool_calls=..., total_usdc=..., settled_at=...)
```

### Credit History

```python
page = await client.get_credit_history()
entries: list[CreditHistoryEntry] = page["items"]
```

### Stripe Top-up

```python
from teardrop import StripeTopupRequest

resp = await client.topup_stripe(StripeTopupRequest(
    amount_usdc=10_000_000,            # 10 USDC
    success_url="https://app.example.com/billing?success=1",
    cancel_url="https://app.example.com/billing",
))
# Redirect user to resp.checkout_url

# Poll for completion
status = await client.get_stripe_topup_status(resp.session_id)
# → StripeTopupStatusResponse(status="complete"|"open"|"expired", amount_usdc=...)
```

### USDC Top-up (on-chain EIP-3009)

```python
from teardrop import UsdcTopupRequest

reqs = await client.get_usdc_topup_requirements()
# → UsdcTopupRequirements(payto_address=..., token_address=..., network=..., chain_id=...,
#                         min_amount_usdc=..., authorization_type="EIP-3009")

result = await client.topup_usdc(UsdcTopupRequest(
    amount_usdc=5_000_000,
    authorization="...",    # EIP-3009 signed authorization
    signature="...",
    tx_hash="0x...",        # optional
))
# → {"credited_usdc": 5000000}
```

### Usage Summary

```python
summary = await client.get_usage(from_date="2026-04-01", to_date="2026-04-30")
# → UsageSummary(total_runs=..., total_tokens_in=..., total_tokens_out=...,
#                total_tool_calls=..., total_cost_usdc=...)
```

---

## Wallets

Link Ethereum wallets to a user account for USDC payments and SIWE authentication.

```python
from teardrop import LinkWalletRequest

# nonce + message + signature follow same SIWE pattern as login
wallet = await client.link_wallet(LinkWalletRequest(
    message="...",
    signature="...",
    nonce="...",
))

wallets: list[Wallet] = await client.get_wallets()

await client.delete_wallet(wallet.id)
```

---

## Org Webhook Tools

Register custom webhook-backed tools that the agent can call during runs.

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
    webhook_secret="whsec_...",             # optional HMAC secret
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
    content="User prefers responses in Spanish.",
    metadata={"user_id": "usr_123"},
    ttl_seconds=86400,          # optional TTL; omit for persistent
))

page = await client.list_memories(limit=50)
entries: list[MemoryEntry] = page.items

await client.delete_memory(entry.id)
```

---

## Marketplace

Browse, publish, and monetise tools on the Teardrop marketplace.

### Browsing (no auth required)

```python
page = await client.get_marketplace_catalog(limit=20, tags=["defi", "payments"])
tools: list[MarketplaceTool] = page["items"]
```

### Author Configuration

```python
config = await client.set_author_config(payout_address="0xYourWallet")
config = await client.get_author_config()
# → AuthorConfig(org_id=..., payout_address=..., is_verified=...)
```

### Earnings & Withdrawal

```python
balance = await client.get_marketplace_balance()
# → {"balance_usdc": 1500000, ...}

page = await client.get_earnings(limit=50)
entries: list[EarningsEntry] = page["items"]

from teardrop import WithdrawRequest
result = await client.withdraw(WithdrawRequest(
    amount_usdc=1_000_000,
    payout_address="0xOptionalOverride",   # omit to use author config address
))
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
| `JwtPayloadBase` | `get_me()` |
| `AgentRunRequest` | `run()` (internal) |
| `SSEEvent` | `run()` yields |
| `BillingBalance` | `get_balance()` |
| `BillingPricingResponse`, `ToolPricing` | `get_pricing()` |
| `BillingHistoryEntry` | `get_billing_history()` |
| `Invoice` | `get_invoices()`, `get_invoice()` |
| `CreditHistoryEntry` | `get_credit_history()` |
| `StripeTopupRequest`, `StripeTopupResponse`, `StripeTopupStatusResponse` | `topup_stripe()`, `get_stripe_topup_status()` |
| `UsdcTopupRequirements`, `UsdcTopupRequest` | `get_usdc_topup_requirements()`, `topup_usdc()` |
| `UsageSummary` | `get_usage()` |
| `Wallet`, `LinkWalletRequest` | `get_wallets()`, `link_wallet()` |
| `AgentCard` | `get_agent_card()` |
| `OrgTool`, `CreateOrgToolRequest`, `UpdateOrgToolRequest` | tool CRUD |
| `OrgMcpServer`, `CreateMcpServerRequest`, `UpdateMcpServerRequest`, `DiscoverMcpToolsResponse`, `McpToolDefinition` | MCP CRUD |
| `MemoryEntry`, `MemoryListResponse`, `StoreMemoryRequest` | memory CRUD |
| `MarketplaceTool`, `AuthorConfig`, `EarningsEntry`, `WithdrawRequest` | marketplace |

Import any model directly:

```python
from teardrop import CreateMcpServerRequest, OrgTool, BillingBalance
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

112 tests covering client methods, streaming, auth, and models.
