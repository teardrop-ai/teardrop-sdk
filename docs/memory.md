# Memory

Store and retrieve persistent memory entries scoped to the org. The agent can
read these during runs to personalize behavior across conversations.

```python
from teardrop import StoreMemoryRequest

entry = await client.create_memory(StoreMemoryRequest(
    content="User prefers responses in Spanish.",  # 1–500 characters
))

entries: list[MemoryEntry] = await client.list_memories(limit=50)

await client.delete_memory(entry.id)
```

---

**Related:** [README](../README.md) · [Agent Runs](agent-runs.md)
