# Agent Wallets

Provision a CDP (Coinbase Developer Platform) smart wallet for the org's
agent, enabling it to sign on-chain transactions autonomously. Distinct from
user-linked [Wallets](wallets.md), which are SIWE-based and tied to a person,
not the org's agent.

```python
wallet = await client.provision_agent_wallet()
# → AgentWallet(id=..., address="0x...", network="base", status="active")

# Fetch with live on-chain balance
wallet = await client.get_agent_wallet(include_balance=True)

# Deactivate (admin only)
await client.deactivate_agent_wallet()
```

---

**Related:** [README](../README.md) · [Wallets](wallets.md) · [Billing](billing.md) (USDC top-up)
