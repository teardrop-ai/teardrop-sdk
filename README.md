# teardrop-sdk

Python SDK for the [Teardrop](https://github.com/teardrop-ai/teardrop) AI agent API.

## Install

```bash
pip install teardrop-sdk
```

## Quick Start

```python
from teardrop import AsyncTeardropClient

async with AsyncTeardropClient(
    "https://api.teardrop.dev",
    email="you@example.com",
    secret="your-password",
) as client:
    async for event in client.run("What is the ETH price on Base?"):
        if event.type == "TEXT_MESSAGE_CONTENT":
            print(event.data.get("delta", ""), end="")
    print()
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
            print(event.data.get("delta", ""), end="")
    print()
```

## Auth Methods

| Method | Constructor args |
|--------|-----------------|
| Email + password | `email=..., secret=...` |
| Client credentials (M2M) | `client_id=..., client_secret=...` |
| Pre-authenticated token | `token=...` |
| SIWE (pre-signed) | Pass `siwe_message` + `siwe_signature` via `authenticate_siwe()` |

## Features

- Async-first with sync wrapper
- Typed Pydantic models for all responses
- SSE streaming with parsed event objects
- Auto token refresh
- Zero langchain dependency
- MCP server management (register external MCP servers as agent tools)

## MCP Server Management

Register external MCP servers so the Teardrop agent can discover and use their tools automatically at run time.

```python
from teardrop import AsyncTeardropClient, CreateMcpServerRequest, parse_mcp_tool_name

async with AsyncTeardropClient("https://api.teardrop.dev", email="...", secret="...") as client:
    # Register a Stripe MCP server
    server = await client.create_mcp_server(CreateMcpServerRequest(
        name="stripe",
        url="https://your-stripe-mcp.example.com/sse",
        auth_type="bearer",
        auth_token="sk-...",
    ))

    # Preview available tools (live probe, no agent run needed)
    discovery = await client.discover_mcp_server_tools(server.id)
    print([t.name for t in discovery.tools])

    # Run the agent — MCP tools are injected automatically
    async for event in client.run("Issue a refund for charge_id ch_abc123"):
        if event.type == "TOOL_CALL_START":
            parsed = parse_mcp_tool_name(event.data["tool_name"])
            if parsed["is_mcp"]:
                print(f"MCP call → {parsed['server']}.{parsed['tool']}")
        if event.type == "TEXT_MESSAGE_CONTENT":
            print(event.data.get("delta", ""), end="")
```

### MCP Tool Naming

MCP server tools appear in SSE events as `{server_name}__{tool_name}` (double underscore). Use `parse_mcp_tool_name()` to identify them:

```python
from teardrop import parse_mcp_tool_name

parse_mcp_tool_name("stripe__create_refund")
# → {"is_mcp": True, "server": "stripe", "tool": "create_refund"}

parse_mcp_tool_name("web_search")
# → {"is_mcp": False}
```

### Behavioural Notes

| Constraint | Detail |
|---|---|
| Quota | 5 active servers per org by default; `422` on breach |
| Cache lag | New/updated servers are live within ~5 min (TTL 300 s); `/discover` bypasses cache |
| Soft-delete | `delete_mcp_server()` sets `is_active=False`; agent stops using tools immediately |
| Auth write-only | `auth_token` is never returned; only `has_auth: bool` is exposed |
| Transport | Streamable HTTP only — stdio MCP servers are not supported |
| SSRF | All URLs are validated server-side; private IPs and localhost are blocked |
