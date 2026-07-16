# MCP Servers

Register external MCP (Model Context Protocol) servers. The agent
auto-discovers their tools at run time and namespaces them as
`{server_name}__{tool_name}`. Covers CRUD, live tool discovery, tool-name
parsing, and operational constraints.

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

## MCP Tool Names in Events

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

## MCP Behavioural Notes

| Constraint | Detail |
|---|---|
| Quota | 5 active servers per org by default; `422` on breach |
| Cache lag | New/updated servers are live within ~5 min (TTL 300 s); `/discover` bypasses cache |
| Auth write-only | `auth_token` is write-only; only `has_auth: bool` is returned |
| Transport | Streamable HTTP only — stdio MCP servers are not supported |
| SSRF | Server-side URL validation blocks private IPs and localhost |

---

**Related:** [README](../README.md) · [Marketplace](marketplace.md) (importing MCP tools for publishing) · [Custom Webhook Tools](custom-tools.md) · [Agent Runs](agent-runs.md)
