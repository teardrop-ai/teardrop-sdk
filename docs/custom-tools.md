# Custom Webhook Tools

Register custom webhook-backed tools for your org that the agent can call
during runs. These are private to your organization and not shared on the
marketplace (unless explicitly published). For comparison with marketplace
tools and MCP servers, see [Marketplace vs. Custom Tools vs. MCP Servers](marketplace.md#marketplace-vs-custom-tools-vs-mcp-servers).

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

## Testing a Webhook Before Registering

Fire a single diagnostic call against a webhook URL — unbilled, does not
write to the audit trail, and bypasses the circuit breaker. Useful for
validating reachability and response shape before calling `create_tool()`.

```python
from teardrop.models import TestWebhookRequest

result = await client.test_webhook(
    TestWebhookRequest(
        webhook_url="https://hooks.example.com/email",
        payload={"to": "a@example.com", "subject": "hi", "body": "hello"},
    )
)
# → TestWebhookResponse(success=True, status_code=200, latency_ms=..., response_body={...}, error=None)
```

---

**Related:** [README](../README.md) · [Marketplace](marketplace.md) · [MCP Servers](mcp-servers.md) · [Agent Runs](agent-runs.md)
