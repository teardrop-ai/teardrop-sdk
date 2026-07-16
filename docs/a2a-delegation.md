# A2A Delegation

Allow other organizations' agents to call your agent on behalf of their users
via the Agent-to-Agent (A2A) protocol. Covers trusted-agent CRUD and
delegation event history.

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

**Related:** [README](../README.md) · [Agent Card](agent-card.md) · [Agent Runs](agent-runs.md)
