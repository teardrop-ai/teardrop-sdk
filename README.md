# teardrop-sdk

Python SDK for the [Teardrop](https://github.com/teardrop-ai/teardrop) AI agent API — async-first HTTP/SSE client for running agents, managing billing/wallets, and extending agent tools (marketplace, custom webhooks, MCP servers).

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

## Documentation

Full usage guides live under [docs/](docs/), one file per feature domain. Each is self-contained with runnable examples.

| Topic | Doc | Covers |
|---|---|---|
| Authentication | [docs/authentication.md](docs/authentication.md) | Email/M2M/SIWE login, registration, org invites, tool discovery |
| Agent Runs | [docs/agent-runs.md](docs/agent-runs.md) | `run()`/`run_sync()`, `tool_policy`, SSE events, x402 retries, exceptions |
| Marketplace | [docs/marketplace.md](docs/marketplace.md) | Browse/subscribe/publish tools, earnings, tool naming |
| Custom Webhook Tools | [docs/custom-tools.md](docs/custom-tools.md) | Org-private webhook tool CRUD |
| MCP Servers | [docs/mcp-servers.md](docs/mcp-servers.md) | Register MCP servers, live discovery, tool naming |
| Billing | [docs/billing.md](docs/billing.md) | Balance, pricing, invoices, Stripe/USDC top-up, usage |
| LLM Configuration | [docs/llm-config.md](docs/llm-config.md) | Provider/model selection, BYOK, routing |
| Model Benchmarks | [docs/model-benchmarks.md](docs/model-benchmarks.md) | Latency/cost/throughput catalogue |
| Wallets | [docs/wallets.md](docs/wallets.md) | Link/list SIWE user wallets |
| Agent Wallets | [docs/agent-wallets.md](docs/agent-wallets.md) | CDP smart wallet for the org's agent |
| Memory | [docs/memory.md](docs/memory.md) | Persistent org memory entries |
| Schedules & Event Triggers | [docs/schedules-and-event-triggers.md](docs/schedules-and-event-triggers.md) | Interval and webhook-triggered runs |
| A2A Delegation | [docs/a2a-delegation.md](docs/a2a-delegation.md) | Trusted-agent delegation |
| Admin Client | [docs/admin.md](docs/admin.md) | All `/admin/*` operations (billing, marketplace, identity, tools, memory, usage) |
| Agent Card | [docs/agent-card.md](docs/agent-card.md) | A2A discovery card |
| Models Reference | [docs/models-reference.md](docs/models-reference.md) | Pydantic model → method map |
| Development | [docs/development.md](docs/development.md) | Dev setup, tests, integration tests |

The canonical, machine-readable API contracts are [spec/openapi.json](spec/openapi.json) (REST schema) and [spec/events.schema.json](spec/events.schema.json) (SSE event payloads) — treat them as the source of truth if a doc and the spec ever disagree.

---

## Authentication

Email/password, M2M client credentials, static token, or SIWE (sign-in with Ethereum) login; registration, org invites, and live tool discovery. See **[docs/authentication.md](docs/authentication.md)**.

---

## Marketplace

Discover, subscribe to, and monetize tools on the Teardrop marketplace — the primary distribution surface for sharing agent tools across orgs and earning usage revenue. See **[docs/marketplace.md](docs/marketplace.md)** for browsing, subscriptions, publishing, earnings, and tool naming.

Also compares **Marketplace vs. Custom Webhook Tools vs. MCP Servers** to help you pick the right extension mechanism.

---

## Agent Runs

Stream agent responses over SSE with `run()`/`run_sync()`, apply per-request tool guardrails, pass extra context, and handle x402 on-chain payment retries and SDK exceptions. See **[docs/agent-runs.md](docs/agent-runs.md)**.

---

## Billing

Balance, pricing, invoices, credit history, Stripe/USDC top-up, and usage summaries. USDC amounts are atomic units (6 decimals); use `format_usdc()`/`parse_usdc()` to convert. See **[docs/billing.md](docs/billing.md)**.

---

## LLM Configuration

Customize which LLM provider and model the agent uses, enable bring-your-own-key (BYOK), or route to self-hosted endpoints. See **[docs/llm-config.md](docs/llm-config.md)**.

---

## Model Benchmarks

Browse model capabilities and operational metrics (latency, cost, throughput) to pick a model programmatically. See **[docs/model-benchmarks.md](docs/model-benchmarks.md)**.

---

## Wallets

Link Ethereum wallets to a user account for USDC payments and SIWE authentication. See **[docs/wallets.md](docs/wallets.md)**.

---

## Custom Webhook Tools

Register org-private webhook-backed tools the agent can call during runs. See **[docs/custom-tools.md](docs/custom-tools.md)**.

---

## MCP Servers

Register external MCP (Model Context Protocol) servers; the agent auto-discovers their tools at run time and namespaces them as `{server_name}__{tool_name}`. See **[docs/mcp-servers.md](docs/mcp-servers.md)**.

---

## Memory

Store and retrieve persistent memory entries scoped to the org; the agent can read these during runs. See **[docs/memory.md](docs/memory.md)**.

---

## Schedules & Event Triggers

Automate agent runs either on a fixed interval (`client.schedules`) or from an external webhook payload (`client.event_triggers`), including signature verification. See **[docs/schedules-and-event-triggers.md](docs/schedules-and-event-triggers.md)**.

---

## A2A Delegation

Allow other organisations' agents to call your agent on behalf of their users. See **[docs/a2a-delegation.md](docs/a2a-delegation.md)**.

---

## Agent Wallets

Provision a CDP smart wallet for the org's agent, enabling it to sign transactions autonomously. See **[docs/agent-wallets.md](docs/agent-wallets.md)**.

---

## Agent Card

Fetch the A2A agent card from `/.well-known/agent-card.json`. See **[docs/agent-card.md](docs/agent-card.md)**.

---

## Models Reference

Full Pydantic v2 model → client method mapping table. See **[docs/models-reference.md](docs/models-reference.md)**.

```python
from teardrop import OrgLlmConfig, ModelBenchmarksResponse, BillingBalance
```

---

## Development

```bash
pip install -e ".[dev]"
pytest
pytest --cov=teardrop --cov-report=term-missing
```

Integration tests make real HTTP requests against the Teardrop API and are skipped automatically unless `TEARDROP_TEST_URL`/`TEARDROP_TEST_EMAIL`/`TEARDROP_TEST_SECRET` are set. See **[docs/development.md](docs/development.md)**.
