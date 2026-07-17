# Marketplace

Discover, subscribe to, and monetize tools on the Teardrop marketplace — a
curated catalogue of reusable agent tools published by the Teardrop community
and core team. Covers browsing, subscriptions, publishing, earnings, and how
marketplace tools surface during agent runs. **The marketplace is Teardrop's
primary product for tool distribution.**

## Three Core Workflows

1. **Browsing** (public, no auth) — Discover tools in the marketplace catalogue
2. **Subscriptions** (auth required) — Subscribe to and use marketplace tools in your agent runs
3. **Publishing & Earnings** (auth required) — Publish your own tools and track revenue

## Browsing Tools (Public)

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

# Fetch a single catalog tool by qualified name parts
tool = await client.get_marketplace_catalog_detail("acme", "web_search")
# → MarketplaceTool

# Public author profile (metadata + published tools)
profile = await client.get_marketplace_author_profile("acme", sort="popularity", limit=20)
```

## Subscriptions & Integration

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

## Publishing & Earnings

### Author Setup

```python
# Configure payout wallet for earnings
config = await client.set_author_config(settlement_wallet="0xYourWalletAddress")
config = await client.get_author_config()
# → AuthorConfig(org_id=..., settlement_wallet="0x...")
```

### Earnings & Revenue Tracking

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

### Withdrawals

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

### Importing Tools From an MCP Server

Publish tools from an already-registered MCP server (see [MCP Servers](mcp-servers.md))
directly to the marketplace, without hand-writing a webhook tool definition.

```python
from teardrop.models import (
    MarketplaceImportPreviewRequest,
    MarketplaceImportPublishRequest,
    MarketplaceImportPublishToolRequest,
)

# 1. Preview importable tools on a registered MCP server
preview = await client.preview_marketplace_import(
    MarketplaceImportPreviewRequest(server_id="mcp-server-123")
)
# → MarketplaceImportPreviewResponse
for tool in preview.tools:
    print(tool.remote_tool_name, tool.proposed_name)

# 2. Publish selected tools as marketplace-visible MCP-backed org tools
res = await client.publish_marketplace_import(
    MarketplaceImportPublishRequest(
        server_id="mcp-server-123",
        tools=[
            MarketplaceImportPublishToolRequest(
                remote_tool_name="search",
                name="web_search",
                description="Search the web",
                base_price_usdc=1_000,
            )
        ],
    )
)
# → MarketplaceImportPublishResponse
```

### Tool Quality Feedback

Submit a ground-truth quality signal for a tool call made within one of your
own runs (scoped to the calling user's invoice history):

```python
from teardrop.models import RunFeedbackRequest

feedback = await client.submit_marketplace_tool_feedback(
    "acme",
    "web_search",
    RunFeedbackRequest(run_id="run-abc123", rating=1, comment="Fast and accurate"),
)
# → MarketplaceToolFeedbackResponse
print(feedback.id, feedback.created_at)
```

## Using Marketplace Tools in Agent Runs

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

### Tool Naming

Marketplace tools are namespaced as `{org_slug}__{tool_name}` in tool call events.

```python
from teardrop import parse_marketplace_tool_name

parsed = parse_marketplace_tool_name("acme__web_search")
# → {"org_slug": "acme", "tool_name": "web_search"}
```

### Billing Errors During Tool Calls

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

## Marketplace vs. Custom Tools vs. MCP Servers

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

**Related:** [README](../README.md) · [Custom Webhook Tools](custom-tools.md) · [MCP Servers](mcp-servers.md) · [Agent Runs](agent-runs.md) · [Billing](billing.md)
