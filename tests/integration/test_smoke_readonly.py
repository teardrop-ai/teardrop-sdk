"""Integration smoke tests — read-only operations only.

These tests make real HTTP requests against the Teardrop API.  They are split
into two tiers:

  Tier 1 — public, no authentication required
  Tier 2 — authenticated GET endpoints (no mutations)

All tests are skipped automatically when the integration environment variables
are not set (handled by tests/integration/conftest.py).
"""

from __future__ import annotations

import pytest

from teardrop.client import AsyncTeardropClient
from teardrop.exceptions import APIError, NotFoundError
from teardrop.models import (
    BillingBalance,
    BillingPricingResponse,
    MeResponse,
    ModelBenchmarksResponse,
    UsageSummary,
)


# ─── Tier 1: public endpoints, no auth ───────────────────────────────────────


class TestPublicEndpoints:
    """Endpoints that require no authentication."""

    async def test_get_pricing(self, async_client: AsyncTeardropClient) -> None:
        result = await async_client.get_pricing()
        assert isinstance(result, BillingPricingResponse)

    async def test_get_model_benchmarks(self, async_client: AsyncTeardropClient) -> None:
        result = await async_client.get_model_benchmarks()
        assert isinstance(result, ModelBenchmarksResponse)
        assert isinstance(result.models, list)

    async def test_get_marketplace_catalog(self, async_client: AsyncTeardropClient) -> None:
        result = await async_client.get_marketplace_catalog()
        assert isinstance(result, dict)
        assert "tools" in result


# ─── Tier 2: authenticated read-only endpoints ────────────────────────────────


class TestAuthenticatedReadOnly:
    """Authenticated GET endpoints that produce no side effects."""

    async def test_get_me(self, async_client: AsyncTeardropClient) -> None:
        result = await async_client.get_me()
        assert isinstance(result, MeResponse)
        assert result.org_id  # Must be non-empty

    async def test_get_balance(self, async_client: AsyncTeardropClient) -> None:
        result = await async_client.get_balance()
        assert isinstance(result, BillingBalance)

    async def test_get_usage(self, async_client: AsyncTeardropClient) -> None:
        result = await async_client.get_usage()
        assert isinstance(result, UsageSummary)

    async def test_get_org_model_benchmarks(self, async_client: AsyncTeardropClient) -> None:
        result = await async_client.get_org_model_benchmarks()
        assert isinstance(result, ModelBenchmarksResponse)

    async def test_get_llm_config(self, async_client: AsyncTeardropClient) -> None:
        """LLM config may not be set; both success and 404 are valid responses."""
        try:
            from teardrop.models import OrgLlmConfig

            result = await async_client.get_llm_config()
            assert isinstance(result, OrgLlmConfig)
        except NotFoundError:
            pass  # No custom LLM config set — valid state

    async def test_get_agent_card(self, async_client: AsyncTeardropClient) -> None:
        """Agent card may not be configured; both success and 404 are valid."""
        try:
            from teardrop.models import AgentCard

            result = await async_client.get_agent_card()
            assert isinstance(result, AgentCard)
        except (NotFoundError, APIError):
            pass  # No agent card configured — valid state

    async def test_get_wallets(self, async_client: AsyncTeardropClient) -> None:
        result = await async_client.get_wallets()
        assert isinstance(result, list)

    async def test_list_tools(self, async_client: AsyncTeardropClient) -> None:
        result = await async_client.list_tools()
        assert isinstance(result, list)

    async def test_list_mcp_servers(self, async_client: AsyncTeardropClient) -> None:
        result = await async_client.list_mcp_servers()
        assert isinstance(result, list)

    async def test_list_memories(self, async_client: AsyncTeardropClient) -> None:
        result = await async_client.list_memories(limit=1)
        assert isinstance(result, list)

    async def test_get_subscriptions(self, async_client: AsyncTeardropClient) -> None:
        result = await async_client.get_subscriptions()
        assert isinstance(result, list)

    async def test_get_earnings(self, async_client: AsyncTeardropClient) -> None:
        result = await async_client.get_earnings(limit=1)
        assert isinstance(result, dict)
        assert "earnings" in result

    async def test_list_trusted_agents(self, async_client: AsyncTeardropClient) -> None:
        result = await async_client.list_trusted_agents()
        assert isinstance(result, list)

    async def test_get_delegations(self, async_client: AsyncTeardropClient) -> None:
        result = await async_client.get_delegations(limit=1)
        assert isinstance(result, list)

    async def test_get_billing_history(self, async_client: AsyncTeardropClient) -> None:
        result = await async_client.get_billing_history(limit=1)
        assert isinstance(result, list)

    async def test_get_credit_history(self, async_client: AsyncTeardropClient) -> None:
        result = await async_client.get_credit_history(limit=1)
        assert isinstance(result, list)
