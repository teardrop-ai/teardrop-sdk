# Agent Card

Fetch the A2A discovery agent card from `/.well-known/agent-card.json`.
Result is cached client-side for 5 minutes.

```python
card = await client.get_agent_card()
# → AgentCard(name=..., description=..., url=..., skills=[...])

# Bypass cache
card = await client.get_agent_card(force_refresh=True)
```

The synchronous client accepts the same `force_refresh` keyword. A forced fetch
replaces the cached card after a successful response; ordinary calls reuse the
five-minute cache.

Alternatively, create a client and pre-warm the cache atomically:

```python
client = await AsyncTeardropClient.from_agent_card("https://api.teardrop.dev", email="...", secret="...")
```

---

**Related:** [README](../README.md) · [A2A Delegation](a2a-delegation.md) · [MCP Servers](mcp-servers.md)
