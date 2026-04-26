"""Tests for LLM Config and Model Benchmarks endpoints."""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from teardrop.client import AsyncTeardropClient, _LLM_CONFIG_TTL, _MODEL_BENCHMARKS_TTL
from teardrop.exceptions import AuthenticationError, NotFoundError, ValidationError
from teardrop.models import (
    MODELS_BY_PROVIDER,
    ModelBenchmarksResponse,
    OrgLlmConfig,
    SetLlmConfigRequest,
)


def _json_response(
    body: dict | list, status: int = 200, headers: dict | None = None
) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        content=json.dumps(body).encode(),
        headers={"content-type": "application/json", **(headers or {})},
        request=httpx.Request("GET", "http://test"),
    )


_ORG_LLM_CONFIG = {
    "org_id": "org-1",
    "provider": "anthropic",
    "model": "claude-haiku-4-5-20251001",
    "has_api_key": False,
    "api_base": None,
    "max_tokens": 4096,
    "temperature": 0.0,
    "timeout_seconds": 120,
    "routing_preference": "default",
    "is_byok": False,
    "created_at": "2026-04-16T00:00:00Z",
    "updated_at": "2026-04-16T00:00:00Z",
}

_BENCHMARKS_RESPONSE = {
    "models": [
        {
            "provider": "anthropic",
            "model": "claude-haiku-4-5-20251001",
            "display_name": "Claude Haiku 4.5",
            "context_window": 200000,
            "supports_tools": True,
            "supports_streaming": True,
            "quality_tier": 2,
            "pricing": {
                "tokens_in_cost_per_1k": 0.08,
                "tokens_out_cost_per_1k": 0.24,
                "tool_call_cost": 0.0,
            },
            "benchmarks": {
                "total_runs_7d": 1250,
                "avg_latency_ms": 485.5,
                "p95_latency_ms": 1200.0,
                "avg_cost_usdc_per_run": 12.5,
                "avg_tokens_per_sec": 45.2,
            },
        }
    ],
    "updated_at": "2026-04-16T00:00:00Z",
}


# ─── GET /llm-config ──────────────────────────────────────────────────────────


class TestGetLlmConfig:
    @pytest.mark.asyncio
    async def test_returns_org_llm_config(self):
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(_ORG_LLM_CONFIG))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                result = await client.get_llm_config()

        assert isinstance(result, OrgLlmConfig)
        assert result.org_id == "org-1"
        assert result.provider == "anthropic"
        assert result.has_api_key is False

    @pytest.mark.asyncio
    async def test_result_is_cached(self):
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(_ORG_LLM_CONFIG))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                await client.get_llm_config()
                await client.get_llm_config()

        # Only one HTTP call despite two method calls.
        assert mock_http.get.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_expires_after_ttl(self):
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(_ORG_LLM_CONFIG))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                await client.get_llm_config()
                # Backdate the cache timestamp beyond TTL.
                cached_val, _ = client._llm_config_cache  # type: ignore[misc]
                client._llm_config_cache = (cached_val, time.time() - _LLM_CONFIG_TTL - 1)
                await client.get_llm_config()

        assert mock_http.get.call_count == 2

    @pytest.mark.asyncio
    async def test_401_raises_authentication_error(self):
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(
            return_value=_json_response({"detail": "Unauthorized"}, status=401)
        )

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                with pytest.raises(AuthenticationError):
                    await client.get_llm_config()


# ─── PUT /llm-config ──────────────────────────────────────────────────────────


class TestSetLlmConfig:
    @pytest.mark.asyncio
    async def test_set_config_returns_org_llm_config(self):
        updated = {**_ORG_LLM_CONFIG, "routing_preference": "cost"}
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.put = AsyncMock(return_value=_json_response(updated))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                result = await client.set_llm_config(
                    provider="anthropic",
                    model="claude-haiku-4-5-20251001",
                    routing_preference="cost",
                )

        assert isinstance(result, OrgLlmConfig)
        assert result.routing_preference == "cost"

    @pytest.mark.asyncio
    async def test_set_config_invalidates_cache(self):
        """After a successful PUT, the cache should hold the new value."""
        initial = _json_response(_ORG_LLM_CONFIG)
        updated_data = {**_ORG_LLM_CONFIG, "model": "claude-sonnet-4-20250514"}
        updated = _json_response(updated_data)

        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=initial)
        mock_http.put = AsyncMock(return_value=updated)

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                # Populate cache with initial value.
                first = await client.get_llm_config()
                assert first.model == "claude-haiku-4-5-20251001"

                # Update — should replace the cache.
                await client.set_llm_config(
                    provider="anthropic", model="claude-sonnet-4-20250514"
                )

                # Next GET should use the cache and NOT hit the network again.
                cached = await client.get_llm_config()
                assert cached.model == "claude-sonnet-4-20250514"
                assert mock_http.get.call_count == 1

    @pytest.mark.asyncio
    async def test_api_key_omitted_when_not_provided(self):
        """When api_key is not passed, the field must be absent from the request body."""
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.put = AsyncMock(return_value=_json_response(_ORG_LLM_CONFIG))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                await client.set_llm_config(
                    provider="anthropic",
                    model="claude-haiku-4-5-20251001",
                )

        call_kwargs = mock_http.put.call_args
        body = call_kwargs.kwargs["json"]
        assert "api_key" not in body

    @pytest.mark.asyncio
    async def test_null_api_key_sent_to_clear_byok(self):
        """When api_key=None is explicitly passed, the field must be sent as null
        so the backend clears BYOK and reverts to the shared platform key."""
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.put = AsyncMock(return_value=_json_response(_ORG_LLM_CONFIG))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                await client.set_llm_config(
                    provider="anthropic",
                    model="claude-haiku-4-5-20251001",
                    api_key=None,
                )

        call_kwargs = mock_http.put.call_args
        body = call_kwargs.kwargs["json"]
        assert "api_key" in body
        assert body["api_key"] is None

    @pytest.mark.asyncio
    async def test_api_key_sent_when_provided(self):
        """When api_key is set, it must appear in the request body (TLS transport)."""
        mock_http = AsyncMock()
        mock_http.is_closed = False
        byok_config = {**_ORG_LLM_CONFIG, "has_api_key": True, "is_byok": True}
        mock_http.put = AsyncMock(return_value=_json_response(byok_config))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                result = await client.set_llm_config(
                    provider="openai",
                    model="gpt-4o",
                    api_key="sk-test-key",
                )

        call_kwargs = mock_http.put.call_args
        body = call_kwargs.kwargs["json"]
        assert body["api_key"] == "sk-test-key"
        assert result.is_byok is True

    def test_invalid_provider_raises_validation_error(self):
        with pytest.raises(Exception):
            SetLlmConfigRequest(provider="unknown-llm", model="some-model")  # type: ignore[arg-type]

    def test_invalid_routing_preference_raises_validation_error(self):
        with pytest.raises(Exception):
            SetLlmConfigRequest(
                provider="anthropic",
                model="claude-haiku-4-5-20251001",
                routing_preference="fastest",  # type: ignore[arg-type]
            )

    def test_temperature_out_of_range_raises(self):
        with pytest.raises(Exception):
            SetLlmConfigRequest(
                provider="anthropic",
                model="claude-haiku-4-5-20251001",
                temperature=3.0,
            )

    def test_max_tokens_out_of_range_raises(self):
        with pytest.raises(Exception):
            SetLlmConfigRequest(
                provider="anthropic",
                model="claude-haiku-4-5-20251001",
                max_tokens=0,
            )

    @pytest.mark.asyncio
    async def test_400_ssrf_raises_api_error(self):
        from teardrop.exceptions import APIError

        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.put = AsyncMock(
            return_value=_json_response({"detail": "SSRF violation"}, status=400)
        )

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                with pytest.raises(APIError):
                    await client.set_llm_config(
                        provider="openai",
                        model="gpt-4o",
                        api_base="http://192.168.1.1:8000/v1",
                    )


# ─── DELETE /llm-config ───────────────────────────────────────────────────────


class TestDeleteLlmConfig:
    @pytest.mark.asyncio
    async def test_returns_deleted_status(self):
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.delete = AsyncMock(return_value=_json_response({"status": "deleted"}))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                result = await client.delete_llm_config()

        assert result == {"status": "deleted"}

    @pytest.mark.asyncio
    async def test_delete_clears_cache(self):
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(_ORG_LLM_CONFIG))
        mock_http.delete = AsyncMock(return_value=_json_response({"status": "deleted"}))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                await client.get_llm_config()
                assert client._llm_config_cache is not None

                await client.delete_llm_config()
                assert client._llm_config_cache is None

    @pytest.mark.asyncio
    async def test_404_raises_not_found(self):
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.delete = AsyncMock(
            return_value=_json_response({"detail": "Not found"}, status=404)
        )

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                with pytest.raises(NotFoundError):
                    await client.delete_llm_config()


# ─── GET /models/benchmarks ───────────────────────────────────────────────────


class TestGetModelBenchmarks:
    @pytest.mark.asyncio
    async def test_returns_benchmarks_response(self):
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(_BENCHMARKS_RESPONSE))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            result = await client.get_model_benchmarks()

        assert isinstance(result, ModelBenchmarksResponse)
        assert len(result.models) == 1
        assert result.models[0].provider == "anthropic"
        assert result.models[0].benchmarks is not None
        assert result.models[0].benchmarks.total_runs_7d == 1250

    @pytest.mark.asyncio
    async def test_result_is_cached(self):
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(_BENCHMARKS_RESPONSE))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            await client.get_model_benchmarks()
            await client.get_model_benchmarks()

        assert mock_http.get.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_expires_after_ttl(self):
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(_BENCHMARKS_RESPONSE))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            await client.get_model_benchmarks()
            # Expire the cache.
            cached_val, _ = client._model_benchmarks_cache  # type: ignore[misc]
            client._model_benchmarks_cache = (
                cached_val,
                time.time() - _MODEL_BENCHMARKS_TTL - 1,
            )
            await client.get_model_benchmarks()

        assert mock_http.get.call_count == 2

    @pytest.mark.asyncio
    async def test_benchmarks_absent_when_fewer_than_ten_runs(self):
        """benchmarks key may be absent for models with < 10 runs."""
        sparse = {
            "models": [
                {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "display_name": "GPT-4o mini",
                    "context_window": 128000,
                    "supports_tools": True,
                    "supports_streaming": True,
                    "quality_tier": 1,
                    "pricing": {
                        "tokens_in_cost_per_1k": 0.15,
                        "tokens_out_cost_per_1k": 0.60,
                        "tool_call_cost": 0.0,
                    },
                    # No "benchmarks" key
                }
            ],
            "updated_at": "2026-04-16T00:00:00Z",
        }
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(sparse))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            result = await client.get_model_benchmarks()

        assert result.models[0].benchmarks is None


# ─── GET /models/benchmarks/org ───────────────────────────────────────────────


class TestGetOrgModelBenchmarks:
    @pytest.mark.asyncio
    async def test_returns_org_benchmarks(self):
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(_BENCHMARKS_RESPONSE))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                result = await client.get_org_model_benchmarks()

        assert isinstance(result, ModelBenchmarksResponse)
        called_url = mock_http.get.call_args.args[0]
        assert called_url.endswith("/models/benchmarks/org")

    @pytest.mark.asyncio
    async def test_org_benchmarks_not_cached(self):
        """Org benchmarks are never cached — always fresh."""
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(_BENCHMARKS_RESPONSE))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                await client.get_org_model_benchmarks()
                await client.get_org_model_benchmarks()

        assert mock_http.get.call_count == 2

    @pytest.mark.asyncio
    async def test_401_raises_authentication_error(self):
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(
            return_value=_json_response({"detail": "Unauthorized"}, status=401)
        )

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                with pytest.raises(AuthenticationError):
                    await client.get_org_model_benchmarks()


# ─── list_supported_providers / list_models_for_provider ─────────────────────


class TestProviderHelpers:
    def test_list_supported_providers(self):
        client = AsyncTeardropClient("http://test", token="tok.en.sig")
        providers = client.list_supported_providers()
        assert set(providers) == {"anthropic", "openai", "google", "openrouter"}

    def test_list_models_for_provider_anthropic(self):
        client = AsyncTeardropClient("http://test", token="tok.en.sig")
        models = client.list_models_for_provider("anthropic")
        assert "claude-haiku-4-5-20251001" in models
        assert "claude-sonnet-4-20250514" in models

    def test_list_models_for_provider_unknown_raises(self):
        client = AsyncTeardropClient("http://test", token="tok.en.sig")
        with pytest.raises(ValueError, match="Unknown provider"):
            client.list_models_for_provider("cohere")

    def test_models_by_provider_constant(self):
        assert "anthropic" in MODELS_BY_PROVIDER
        assert "openai" in MODELS_BY_PROVIDER
        assert "google" in MODELS_BY_PROVIDER


# ─── clear_llm_api_key ────────────────────────────────────────────────────────


class TestClearLlmApiKey:
    @pytest.mark.asyncio
    async def test_sends_null_api_key(self):
        """clear_llm_api_key() must send api_key: null so the backend reverts to shared key."""
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.put = AsyncMock(return_value=_json_response(_ORG_LLM_CONFIG))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                await client.clear_llm_api_key(
                    provider="anthropic",
                    model="claude-haiku-4-5-20251001",
                )

        call_kwargs = mock_http.put.call_args
        body = call_kwargs.kwargs["json"]
        assert "api_key" in body
        assert body["api_key"] is None

    @pytest.mark.asyncio
    async def test_returns_org_llm_config(self):
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.put = AsyncMock(return_value=_json_response(_ORG_LLM_CONFIG))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                result = await client.clear_llm_api_key(
                    provider="anthropic",
                    model="claude-haiku-4-5-20251001",
                )

        assert isinstance(result, OrgLlmConfig)
