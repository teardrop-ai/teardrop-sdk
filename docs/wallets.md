# Wallets

Link Ethereum wallets to a user account via SIWE (Sign-In With Ethereum) for
USDC payments and wallet-based authentication. For the org-owned agent
signing wallet, see [Agent Wallets](agent-wallets.md).

```python
from teardrop import LinkWalletRequest

wallet = await client.link_wallet(LinkWalletRequest(
    siwe_message="...",
    siwe_signature="...",
))

wallets: list[Wallet] = await client.get_wallets()

await client.delete_wallet(wallet.id)
```

---

**Related:** [README](../README.md) · [Agent Wallets](agent-wallets.md) · [Authentication](authentication.md) (SIWE login flow) · [Billing](billing.md) (USDC top-up)
