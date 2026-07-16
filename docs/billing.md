# Billing

Covers organization credit balance, tool/run pricing, billing and credit
history, invoices, Stripe and on-chain USDC top-ups, and usage summaries.
USDC amounts throughout the SDK are atomic units (6 decimals).

## Balance

```python
balance = await client.get_balance()
# → BillingBalance(org_id=..., balance_usdc=5000, spending_limit_usdc=10000, is_paused=False)
```

Use `format_usdc()` / `parse_usdc()` helpers to convert atomic units:

```python
from teardrop import format_usdc, parse_usdc
print(format_usdc(5_000_000))  # → "5.000000"
print(parse_usdc("1.50"))      # → 1500000
```

## Pricing

```python
pricing = await client.get_pricing()   # no auth required
for tool in pricing.tools:
    print(tool.tool_name, tool.price_usdc)
```

## Billing History

```python
entries: list[BillingHistoryEntry] = await client.get_billing_history(limit=50)
```

## Invoices

```python
# Flat list
invoices: list[Invoice] = await client.get_invoices(limit=20)

# Single run invoice
invoice = await client.get_invoice(run_id)
# → Invoice(run_id=..., tokens_in=..., tokens_out=..., tool_calls=..., total_usdc=..., settled_at=...)
```

## Credit History

```python
# Filter by "topup" or "debit"
entries = await client.get_credit_history(operation="debit", limit=50)

for entry in entries:
    # operation: "debit" | "topup"
    # balance_usdc_after: current balance after this transaction
    # reason: human-readable explanation (e.g., "Agent run run-123")
    print(f"{entry.operation}: {entry.amount_usdc} (Balance: {entry.balance_usdc_after})")
    if entry.reason:
        print(f"  Reason: {entry.reason}")
```

## Stripe Top-up

```python
from teardrop import StripeTopupRequest

resp = await client.topup_stripe(StripeTopupRequest(
    amount_cents=1000,                             # $10.00 in cents
    return_url="https://app.example.com/billing",
))
# resp.client_secret — pass to Stripe.js to confirm payment
# resp.session_id   — use to poll status

# Poll for completion
status = await client.get_stripe_topup_status(resp.session_id)
# → StripeTopupStatusResponse(status="complete"|"open"|"expired", new_balance_fmt="$15.00")
```

## USDC Top-up (on-chain x402)

```python
from teardrop import UsdcTopupRequest

# Fetch payment requirements for a given amount
reqs = await client.get_usdc_topup_requirements(amount_usdc=5_000_000)
# → UsdcTopupRequirements(accepts=[{...}], x402Version=2)

result = await client.topup_usdc(UsdcTopupRequest(
    amount_usdc=5_000_000,
    payment_header="...",   # x402 payment header value
))
```

## Usage Summary

```python
summary = await client.get_usage(start="2026-04-01", end="2026-04-30")
# → UsageSummary(total_runs=..., total_tokens_in=..., total_tokens_out=...,
#                total_tool_calls=..., total_duration_ms=...)
```

Usage events in the `client.run()` stream also include cache performance metrics:
- `cache_read_tokens`: Input tokens served from cache (cheaper/faster).
- `cache_creation_tokens`: Tokens written to the cache for future use.

---

**Related:** [README](../README.md) · [Agent Runs](agent-runs.md) (x402 retries) · [Marketplace](marketplace.md) (author earnings) · [spec/openapi.json](../spec/openapi.json)
