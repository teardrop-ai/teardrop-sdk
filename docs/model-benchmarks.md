# Model Benchmarks

Browse model capabilities and operational metrics (latency, cost, throughput)
across your org's usage, or the public cross-org catalogue. Useful for
programmatically selecting a model by cost or speed before calling
[`set_llm_config`](llm-config.md).

## Public Model Catalogue

```python
benchmarks = await client.get_model_benchmarks()  # no auth required
# → ModelBenchmarksResponse(
#     models=[
#       ModelInfo(
#         provider="anthropic",
#         model="claude-haiku-4-5-20251001",
#         display_name="Claude Haiku 4.5",
#         context_window=200000,
#         supports_tools=True,
#         supports_streaming=True,
#         quality_tier=2,
#         pricing=ModelPricing(
#           tokens_in_cost_per_1k=0.08,
#           tokens_out_cost_per_1k=0.24,
#           tool_call_cost=0.0
#         ),
#         benchmarks=ModelRunBenchmarks(
#           total_runs_7d=1250,
#           avg_latency_ms=485.5,
#           p95_latency_ms=1200.0,
#           avg_cost_usdc_per_run=12.5,
#           avg_tokens_per_sec=45.2
#         )
#       ),
#       ...
#     ],
#     updated_at="2026-04-16T12:00:00Z"
#   )
```

**Notes**:
- Results are cached client-side for 10 minutes.
- `benchmarks` field is `None` for models with < 10 runs in the 7-day window.
- `pricing` is always present (sourced from current pricing rules).

## Org-Scoped Benchmarks

```python
org_benchmarks = await client.get_org_model_benchmarks()  # auth required
```

Same response structure as public benchmarks, but filtered to your org's usage only. **Not cached** — always fresh query. Returns empty model list if org has no usage data.

## Use Case: Choosing Models

```python
benchmarks = await client.get_model_benchmarks()

# Find cheapest
cheapest = min(
    (m for m in benchmarks.models if m.benchmarks),
    key=lambda m: m.pricing.tokens_in_cost_per_1k + m.pricing.tokens_out_cost_per_1k
)

# Find fastest
fastest = min(
    (m for m in benchmarks.models if m.benchmarks),
    key=lambda m: m.benchmarks.avg_latency_ms
)

print(f"Cheapest: {cheapest.model}")
print(f"Fastest: {fastest.model}")

# Configure agent to use cheapest
await client.set_llm_config(
    provider=cheapest.provider,
    model=cheapest.model,
    routing_preference="cost",
)
```

---

**Related:** [README](../README.md) · [LLM Configuration](llm-config.md) · [Billing](billing.md)
