"""Integration tests — Marketplace end-to-end user flow.

Subscribes to a community tool and asserts it becomes usable in the org.
Write operations are self-cleaning.

Skipped automatically when integration env vars are not set.
"""

from __future__ import annotations

from typing import Optional

import pytest

from teardrop.client import AsyncTeardropClient
from teardrop.exceptions import ConflictError, NotFoundError, ValidationError
from teardrop.models import MarketplaceSubscription, MarketplaceTool


async def _first_unsubscribed_community_tool(
    client: AsyncTeardropClient,
) -> Optional[MarketplaceTool]:
    """Return the first community tool the account is not already subscribed to."""
    catalog = await client.get_marketplace_catalog(limit=100)
    subscriptions = await client.get_subscriptions()
    subscribed_names = {s.qualified_tool_name for s in subscriptions.subscriptions}
    return next(
        (
            tool
            for tool in catalog.tools
            if tool.tool_type == "community" and tool.name not in subscribed_names
        ),
        None,
    )


async def _cleanup_subscription(client: AsyncTeardropClient, subscription_id: str) -> None:
    try:
        await client.unsubscribe(subscription_id)
    except NotFoundError:
        pass


class TestMarketplaceEndToEnd:
    """Full marketplace journey: subscribe -> tool usable -> unsubscribe."""

    async def test_subscribed_tool_appears_in_org_tools(
        self, async_client: AsyncTeardropClient
    ) -> None:
        """After subscribing to a marketplace tool, it is listed in org tools."""
        tool = await _first_unsubscribed_community_tool(async_client)
        if tool is None:
            pytest.skip("No unsubscribed community tools available in catalog")

        subscription: Optional[MarketplaceSubscription] = None
        try:
            subscription = await async_client.subscribe(tool.name)
            assert isinstance(subscription, MarketplaceSubscription)
            assert subscription.qualified_tool_name == tool.name
            assert subscription.is_active

            tools = await async_client.list_tools()
            assert any(t.name == tool.name for t in tools), (
                f"Subscribed tool {tool.name} not found in org tool list"
            )
        except (ConflictError, ValidationError) as exc:
            pytest.skip(f"Could not subscribe to tool: {exc}")
        finally:
            if subscription is not None:
                await _cleanup_subscription(async_client, subscription.id)
