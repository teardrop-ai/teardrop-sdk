"""LLM configuration and model benchmark client methods."""

from __future__ import annotations

import time
from typing import Any

from teardrop.client._core import _LLM_CONFIG_TTL, _MODEL_BENCHMARKS_TTL, _UNSET
from teardrop.models import (
    MODELS_BY_PROVIDER,
    ModelBenchmarksResponse,
    OrgLlmConfig,
    SetLlmConfigRequest,
)


class _LlmMixin:
    async def get_llm_config(self) -> OrgLlmConfig:
        now = time.time()
        if self._llm_config_cache is not None and now < self._llm_config_cache[1] + _LLM_CONFIG_TTL:
            return self._llm_config_cache[0]

        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/llm-config", headers=await self._headers())
        self._raise_for_status(resp)
        config = OrgLlmConfig.model_validate(resp.json())
        self._llm_config_cache = (config, now)
        return config

    async def set_llm_config(
        self,
        *,
        provider: str,
        model: str,
        routing_preference: str = "default",
        api_key: str | None = _UNSET,
        api_base: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        timeout_seconds: int = 120,
    ) -> OrgLlmConfig:
        req_kwargs: dict[str, Any] = dict(
            provider=provider,
            model=model,
            api_base=api_base,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
            routing_preference=routing_preference,
        )
        if api_key is not _UNSET:
            req_kwargs["api_key"] = api_key
        request = SetLlmConfigRequest(**req_kwargs)
        body = request.model_dump(exclude_none=True)
        if "api_key" in request.model_fields_set and request.api_key is None:
            body["api_key"] = None

        http = await self._get_http()
        resp = await http.put(
            f"{self._base_url}/llm-config",
            json=body,
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        config = OrgLlmConfig.model_validate(resp.json())
        self._llm_config_cache = (config, time.time())
        return config

    async def clear_llm_api_key(
        self,
        *,
        provider: str,
        model: str,
        routing_preference: str = "default",
        api_base: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        timeout_seconds: int = 120,
    ) -> OrgLlmConfig:
        return await self.set_llm_config(
            provider=provider,
            model=model,
            routing_preference=routing_preference,
            api_key=None,
            api_base=api_base,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
        )

    async def delete_llm_config(self) -> dict[str, Any]:
        http = await self._get_http()
        resp = await http.delete(f"{self._base_url}/llm-config", headers=await self._headers())
        self._raise_for_status(resp)
        self._llm_config_cache = None
        return resp.json()

    async def get_model_benchmarks(self) -> ModelBenchmarksResponse:
        now = time.time()
        if (
            self._model_benchmarks_cache is not None
            and now < self._model_benchmarks_cache[1] + _MODEL_BENCHMARKS_TTL
        ):
            return self._model_benchmarks_cache[0]

        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/models/benchmarks")
        self._raise_for_status(resp)
        result = ModelBenchmarksResponse.model_validate(resp.json())
        self._model_benchmarks_cache = (result, now)
        return result

    async def get_org_model_benchmarks(self) -> ModelBenchmarksResponse:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/models/benchmarks/org", headers=await self._headers()
        )
        self._raise_for_status(resp)
        return ModelBenchmarksResponse.model_validate(resp.json())

    def list_supported_providers(self) -> list[str]:
        return list(MODELS_BY_PROVIDER.keys())

    def list_models_for_provider(self, provider: str) -> list[str]:
        if provider not in MODELS_BY_PROVIDER:
            raise ValueError(
                f"Unknown provider {provider!r}. Supported: {list(MODELS_BY_PROVIDER.keys())}"
            )
        return list(MODELS_BY_PROVIDER[provider])
