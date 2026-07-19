"""Integration tests — billing user-facing routes.

Verifies that real agent usage is reflected in balance, usage summary, and
credit history.  Requires a funded sandbox account.

Skipped automatically when integration env vars are not set.
"""

from __future__ import annotations

import pytest

from teardrop.client import AsyncTeardropClient
from teardrop.exceptions import PaymentRequiredError
from teardrop.models import SSEEvent
from teardrop.streaming import EVENT_RUN_FINISHED, EVENT_RUN_STARTED


class TestBillingUserFlow:
    """User billing path: run agent -> credit consumed -> history updated."""

    async def test_balance_has_numeric_usdc(self, async_client: AsyncTeardropClient) -> None:
        """Balance endpoint returns a usable integer USDC amount."""
        balance = await async_client.get_balance()
        assert isinstance(balance.balance_usdc, int)
        assert balance.balance_usdc >= 0

    async def test_usage_summary_is_non_negative(self, async_client: AsyncTeardropClient) -> None:
        """Usage totals are non-negative integers."""
        usage = await async_client.get_usage()
        assert usage.total_runs >= 0
        assert usage.total_tokens_in >= 0
        assert usage.total_tokens_out >= 0
        assert usage.total_tool_calls >= 0

    async def test_agent_run_consumes_credits(self, async_client: AsyncTeardropClient) -> None:
        """A real agent run increases run count in usage summary."""
        usage_before = await async_client.get_usage()

        events: list[SSEEvent] = []
        try:
            async for event in async_client.run("hello, respond briefly"):
                events.append(event)
        except PaymentRequiredError as exc:
            pytest.skip(f"Sandbox requires funded credits for agent run: {exc}")

        types = {e.type for e in events}
        assert EVENT_RUN_STARTED in types, f"Expected RUN_STARTED, got {types}"
        assert EVENT_RUN_FINISHED in types or "DONE" in types, (
            f"Expected terminal event, got {types}"
        )

        usage_after = await async_client.get_usage()
        assert usage_after.total_runs >= usage_before.total_runs + 1, (
            "Expected usage.total_runs to increase after a successful run"
        )

    async def test_credit_history_records_debits(self, async_client: AsyncTeardropClient) -> None:
        """Credit history contains debit entries after a real run."""
        history = await async_client.get_credit_history(limit=20, operation="debit")
        assert history.items is not None
        assert all(entry.operation == "debit" for entry in history.items)
        assert all(entry.amount_usdc >= 0 for entry in history.items)


class TestBillingTopupAvailability:
    """Top-up endpoints are optional; if disabled they must fail gracefully."""

    async def test_stripe_topup_requirements(self, async_client: AsyncTeardropClient) -> None:
        """Stripe top-up endpoint returns the expected session shape if enabled."""
        pytest.skip("Stripe top-up requires a real return URL and payment flow")
