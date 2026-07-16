# Agent Runs

Covers `client.run()` / `client.run_sync()` streaming execution, per-request
tool guardrails (`ToolPolicy`), passing extra context, the `SSEEvent` shape and
event-type catalogue, x402 on-chain payment retries, and the SDK exception
hierarchy for error handling.

## Running the Agent

```python
async for event in client.run(
    "Summarise the top DeFi news today",
    thread_id="conv-abc123",          # optional; uuid generated if omitted
    emit_ui=True,                     # set to False to disable SURFACE_UPDATE events
    tool_policy={"exclude_names": ["platform/web_search"]}, # dynamically disable tools
):
    print(event.type, event.data)
```

`run()` is an async generator that yields `SSEEvent` objects. The sync equivalent `run_sync()` blocks and returns `list[SSEEvent]`.

## Dynamic Guardrails (`tool_policy`)

You can dynamically restrict an agent's tools on a per-request basis. This is useful for blocking internet access or high-cost tools for specific user segments without changing the agent's global configuration.

```python
from teardrop import ToolPolicy

policy = ToolPolicy(exclude_names=["platform/web_search", "acme/internal_crm"])
async for event in client.run("Hello!", tool_policy=policy):
    ...
```

**Available Tools**: The agent automatically discovers and can call:
- Built-in Teardrop tools
- Marketplace tools you're subscribed to (see [Marketplace](marketplace.md))
- Custom webhook tools registered in your org (see [Custom Webhook Tools](custom-tools.md))
- MCP servers you've registered (see [MCP Servers](mcp-servers.md))

## Passing Context

```python
async for event in client.run(
    "Summarise the top DeFi news today",
    context={"user_timezone": "Europe/Berlin"},   # optional extra context dict
    thread_id="conv-abc123",
):
    ...
```

## SSEEvent Shape

```python
class SSEEvent:
    type: str            # see Event Types below
    data: dict[str, Any]
    id: str              # SSE stream ID (for resumption)
    retry: int | None    # retry interval in ms, if set by server
```

## Event Types

| `event.type` | `event.data` keys | Notes |
|---|---|---|
| `RUN_STARTED` | `run_id`, `thread_id` | First event of every run |
| `TEXT_MESSAGE_START` | `message_id` | Streaming text turn begins |
| `TEXT_MESSAGE_CONTENT` | `delta` | Streaming text chunk |
| `TEXT_MESSAGE_END` | `message_id` | Streaming text turn ends |
| `TOOL_CALL_START` | `tool_call_id`, `tool_name`, `args` | Agent is calling a tool |
| `TOOL_CALL_END` | `tool_call_id`, `result` | Tool returned |
| `SURFACE_UPDATE` | `surface`, `content` | UI surface payload |
| `USAGE_SUMMARY` | `tokens_in`, `tokens_out`, `tool_calls`, `cache_read_tokens`, `cache_creation_tokens` | Per-run token usage |
| `BILLING_SETTLEMENT` | `run_id`, `cost_usdc` | Credit deducted |
| `ERROR` | `message`, `code` | Non-fatal error during run |
| `DONE` | *(empty)* | Stream complete |

## x402 On-chain Payments

If the agent returns a `402 Payment Required`, the SDK raises `PaymentRequiredError`. Extract the requirements and resolve the payment externally, then retry the run passing the resulting x402 `payment_header`:

```python
from teardrop.exceptions import PaymentRequiredError

try:
    async for event in client.run("..."):
        ...
except PaymentRequiredError as e:
    # Resolve the payment using e.requirements, then retry:
    async for event in client.run(
        "...",
        payment_header="sig_...",  # X-Payment header value
        emit_ui=False,             # optional: disable SURFACE_UPDATE events (default: True)
    ):
        ...
```

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

**Related:** [README](../README.md) · [Marketplace](marketplace.md) · [Billing](billing.md) · [spec/events.schema.json](../spec/events.schema.json)
