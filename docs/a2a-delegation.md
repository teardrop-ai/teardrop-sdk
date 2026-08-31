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

Delegation records expose the backend task classification as
`event.task_type`, alongside `run_id`, `task_status`, and billing details.
## Delivery Tracking & Review (spec 1.6.0)

Delegation events now carry delivery-tracking fields: `delivery_status`,
`delivery_error`, `delivery_resolved_at`, and `delivery_settlement_tx`.

### Async task status

```python
# Poll the status of an async A2A task
status = await client.get_message_status(task_id)
print(status["status"])
```

### Admin delivery review

Ambiguous deliveries (e.g. a settlement whose outcome was never observed) can
be listed and resolved by admins without re-dispatching the task:

```python
items = await admin.admin_list_possibly_delivered_delegations(org_id="org-1")
for item in items:
    print(item.id, item.delivery_status, item.refund_status, item.amount_usdc)

result = await admin.admin_resolve_a2a_delegation(
    item.id,
    ResolveA2ADelegationRequest(
        org_id=item.org_id,
        outcome="confirmed",          # or "failed"
        settlement_tx="0x" + "a" * 64,  # optional on-chain settlement proof
    ),
)
print(result.refund_status)  # "cancelled" | "refunded"
```
---

**Related:** [README](../README.md) · [Agent Card](agent-card.md) · [Agent Runs](agent-runs.md)
