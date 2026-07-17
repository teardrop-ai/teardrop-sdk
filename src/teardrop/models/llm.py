"""LLM configuration and model benchmark models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ProviderType = Literal["anthropic", "openai", "google", "openrouter"]
RoutingPreference = Literal["default", "cost", "speed", "quality"]

MODELS_BY_PROVIDER: dict[str, list[str]] = {
    "anthropic": ["claude-haiku-4-5-20251001", "claude-sonnet-4-20250514"],
    "openai": ["gpt-4o-mini", "gpt-4o"],
    "google": ["gemini-2.0-flash", "gemini-2.5-pro"],
    "openrouter": [],
}


class OrgLlmConfig(BaseModel):
    """Org LLM configuration as returned by GET /llm-config and PUT /llm-config."""

    org_id: str = ""
    provider: str = ""
    model: str = ""
    has_api_key: bool = False
    api_base: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.0
    timeout_seconds: int = 120
    routing_preference: str = "default"
    is_byok: bool = False
    created_at: str = ""
    updated_at: str = ""

    model_config = {"extra": "allow"}


class SetLlmConfigRequest(BaseModel):
    """Request body for PUT /llm-config."""

    provider: ProviderType
    model: str
    api_key: str | None = None
    api_base: str | None = None
    max_tokens: int = Field(default=4096, ge=1, le=200_000)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    timeout_seconds: int = Field(default=120, ge=1)
    routing_preference: RoutingPreference = "default"


class ModelPricing(BaseModel):
    tokens_in_cost_per_1k: float = 0.0
    tokens_out_cost_per_1k: float = 0.0
    tool_call_cost: float = 0.0


class ModelRunBenchmarks(BaseModel):
    total_runs_7d: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    avg_cost_usdc_per_run: float = 0.0
    avg_tokens_per_sec: float = 0.0


class ModelInfo(BaseModel):
    """A single model entry in the benchmarks catalogue."""

    provider: str = ""
    model: str = ""
    display_name: str = ""
    context_window: int = 0
    supports_tools: bool = False
    supports_streaming: bool = False
    quality_tier: int = 0
    knowledge_cutoff: str = ""
    training_cutoff_note: str = ""
    pricing: ModelPricing = Field(default_factory=ModelPricing)
    benchmarks: ModelRunBenchmarks | None = None

    model_config = {"extra": "allow"}


class ModelBenchmarksResponse(BaseModel):
    """Response for GET /models/benchmarks and GET /models/benchmarks/org."""

    models: list[ModelInfo]
    updated_at: str = ""


class LlmConfigResponse(OrgLlmConfig):
    """Alias matching the OpenAPI schema name for /llm-config endpoints."""

    provider: str
    model: str
    configured: bool


class LlmConfigDeletedResponse(BaseModel):
    """Response from DELETE /llm-config."""

    org_id: str = ""
    status: str
    deleted_at: str = ""

    model_config = {"extra": "allow"}
