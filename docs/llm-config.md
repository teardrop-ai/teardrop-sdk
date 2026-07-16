# LLM Configuration

Customize which LLM provider and model the agent uses, enable bring-your-own-key
(BYOK), or route to self-hosted endpoints. Configuration is org-scoped, cached
client-side for 5 minutes, and persists across runs.

## Get Current Config

```python
config = await client.get_llm_config()
# → OrgLlmConfig(
#     org_id=..., provider="anthropic", model="claude-haiku-4-5-20251001",
#     has_api_key=False, api_base=None, max_tokens=4096, temperature=0.0,
#     routing_preference="default", is_byok=False, created_at=..., updated_at=...
#   )
```

## Set LLM Config

```python
from teardrop import SetLlmConfigRequest

config = await client.set_llm_config(
    provider="anthropic",                          # "anthropic" | "openai" | "google" | "openrouter"
    model="claude-sonnet-4-20250514",
    routing_preference="cost",                     # "default" | "cost" | "speed" | "quality"
    api_key=None,                                  # optional BYOK key (TLS-only, never logged)
    api_base=None,                                 # optional self-hosted endpoint (vLLM/Ollama)
    max_tokens=4096,                               # 1–200,000
    temperature=0.0,                               # 0.0–2.0
    timeout_seconds=120,
)
```

**Notes**:
- Pass `api_key=None` (or omit) to preserve an existing stored key.
- When `api_key` is provided, it is encrypted at rest and never returned (only `has_api_key: true` is visible).
- `api_base` is validated for SSRF; private IPs are rejected unless the backend explicitly allows them.
- `routing_preference="cost"` enables smart routing to find the cheapest model in a pool.
- Cache is invalidated on successful update.

## Delete LLM Config

```python
await client.delete_llm_config()
# → {"status": "deleted"}
```

Reverts the org to global default LLM config. Returns `404` if no config exists (safe to call idempotently).

## Supported Providers & Models

```python
providers = client.list_supported_providers()
# → ["anthropic", "openai", "google", "openrouter"]

models = client.list_models_for_provider("anthropic")
# → ["claude-haiku-4-5-20251001", "claude-sonnet-4-20250514"]

# Inspect the constant directly
from teardrop import MODELS_BY_PROVIDER
print(MODELS_BY_PROVIDER)
```

---

**Related:** [README](../README.md) · [Model Benchmarks](model-benchmarks.md) · [Agent Runs](agent-runs.md)
