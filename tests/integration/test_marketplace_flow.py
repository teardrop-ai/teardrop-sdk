"""Integration tests — Marketplace catalog and subscriptions.

Covers catalog browsing (public, filtered, paginated, sorted) and the
subscribe/unsubscribe round-trip.  Write operations are self-cleaning:
subscriptions created in tests are always deleted in a ``finally`` block.

Skipped automatically when integration env vars are not set.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest
import pytest_asyncio

from teardrop.client import AsyncTeardropClient
from teardrop.exceptions import ConflictError, NotFoundError, ValidationError
from teardrop.models import MarketplaceSubscription, MarketplaceTool


# ─── Helpers ──────────────────────────────────────────────────────────────────


async def _first_catalog_tool(client: AsyncTeardropClient) -> Optional[MarketplaceTool]:
    """Return the first tool from the marketplace catalog, or None if empty."""
    result = await client.get_marketplace_catalog(limit=1)
    tools: List[MarketplaceTool] = result.get("tools", [])
    return tools[0] if tools else None


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="function")
async def subscribed_subscription(
    async_client: AsyncTeardropClient,
) -> MarketplaceSubscription:
    """Subscribe to the first catalog tool; clean up after each test."""
    tool = await _first_catalog_tool(async_client)
    if tool is None:
        pytest.skip("No marketplace tools available to subscribe to")

    subscription: Optional[MarketplaceSubscription] = None
    try:
        subscription = await async_client.subscribe(tool.name)
        yield subscription
    except ConflictError:
        # Already subscribed — find the existing subscription and yield it
        subs = await async_client.get_subscriptions()
        existing = next(
            (s for s in subs if s.qualified_tool_name == tool.name), None
        )
        if existing is None:
            pytest.skip(
                "Already subscribed but could not locate existing subscription"
            )
        yield existing
        return  # Don't unsubscribe — we didn't create it
    except ValidationError:
        pytest.skip("Tool not subscribable (server returned 422)")
    finally:
        if subscription is not None:
            try:
                await async_client.unsubscribe(subscription.id)
            except Exception:
                pass  # Best-effort cleanup


# ─── Catalog tests ────────────────────────────────────────────────────────────


class TestMarketplaceCatalog:
    async def test_catalog_returns_tools(
        self, async_client: AsyncTeardropClient
    ) -> None:
        """Catalog response contains a 'tools' list of MarketplaceTool objects."""
        result = await async_client.get_marketplace_catalog()
        assert "tools" in result
        tools: List[Any] = result["tools"]
        assert isinstance(tools, list)
        for tool in tools:
            assert isinstance(tool, MarketplaceTool)
            assert tool.name
            assert tool.description

    async def test_catalog_no_auth_required(
        self, integration_url: str
    ) -> None:
        """Marketplace catalog is accessible without authentication."""
        public_client = AsyncTeardropClient(integration_url)
        try:
            result = await public_client.get_marketplace_catalog()
        finally:
            await public_client.close()
        assert "tools" in result
        assert isinstance(result["tools"], list)

    async def test_catalog_platform_filter(
        self, async_client: AsyncTeardropClient
    ) -> None:
        """Filtering by org_slug='platform' returns only platform tools."""
        result = await async_client.get_marketplace_catalog(org_slug="platform")
        tools: List[MarketplaceTool] = result.get("tools", [])
        for tool in tools:
            # Qualified name format is "{org_slug}/{tool_name}"
            assert tool.name.startswith("platform/") or tool.author_slug == "platform", (
                f"Expected platform tool, got name={tool.name!r} author_slug={tool.author_slug!r}"
            )

    async def test_catalog_pagination(
        self, async_client: AsyncTeardropClient
    ) -> None:
        """limit=1 produces a response with next_cursor key present."""
        result = await async_client.get_marketplace_catalog(limit=1)
        assert "next_cursor" in result, (
            "Paginated catalog response must include 'next_cursor' key"
        )
        cursor = result["next_cursor"]
        if cursor is not None:
            # If there's a next page, fetching it must also return tools
            page2 = await async_client.get_marketplace_catalog(limit=1, cursor=cursor)
            assert "tools" in page2
            assert isinstance(page2["tools"], list)

    async def test_catalog_sort_by_price(
        self, async_client: AsyncTeardropClient
    ) -> None:
        """sort='price_asc' parameter is accepted without error."""
        result = await async_client.get_marketplace_catalog(sort="price_asc", limit=10)
        assert "tools" in result
        assert isinstance(result["tools"], list)


# ─── Subscription tests ───────────────────────────────────────────────────────


class TestMarketplaceSubscriptions:
    async def test_subscriptions_list_shape(
        self, async_client: AsyncTeardropClient
    ) -> None:
        """get_subscriptions() returns a list of MarketplaceSubscription objects."""
        subs = await async_client.get_subscriptions()
        assert isinstance(subs, list)
        for sub in subs:
            assert isinstance(sub, MarketplaceSubscription)
            assert sub.id
            assert sub.qualified_tool_name

    async def test_subscribe_and_unsubscribe(
        self, async_client: AsyncTeardropClient
    ) -> None:
        """Full subscribe→verify→unsubscribe round-trip for a catalog tool."""
        tool = await _first_catalog_tool(async_client)
        if tool is None:
            pytest.skip("No marketplace tools available")

        subscription: Optional[MarketplaceSubscription] = None
        try:
            subscription = await async_client.subscribe(tool.name)
            assert isinstance(subscription, MarketplaceSubscription)
            assert subscription.id
            assert subscription.qualified_tool_name == tool.name
            assert subscription.is_active

            # Verify it appears in the subscriptions list
            subs = await async_client.get_subscriptions()
            ids = [s.id for s in subs]
            assert subscription.id in ids, (
                f"Subscription {subscription.id} not found in list after subscribe"
            )
        except ConflictError:
            pytest.skip("Test account already subscribed to this tool")
        except ValidationError as exc:
            pytest.skip(f"Tool not subscribable (server returned 422): {exc}")
        finally:
            if subscription is not None:
                try:
                    await async_client.unsubscribe(subscription.id)
                except Exception:
                    pass

    async def test_subscribe_same_tool_twice(
        self, async_client: AsyncTeardropClient
    ) -> None:
        """Subscribing to the same tool twice returns existing sub or raises ConflictError."""
        tool = await _first_catalog_tool(async_client)
        if tool is None:
            pytest.skip("No marketplace tools available")

        subscription: Optional[MarketplaceSubscription] = None
        try:
            try:
                subscription = await async_client.subscribe(tool.name)
            except ConflictError:
                pytest.skip("Test account already subscribed; skipping double-subscribe test")
            except ValidationError:
                pytest.skip("Tool not subscribable (server returned 422); skipping double-subscribe test")

            # Second subscribe — must either succeed (idempotent) or raise ConflictError
            try:
                second = await async_client.subscribe(tool.name)
                # Idempotent: OK. Verify it points to the same tool.
                assert second.qualified_tool_name == tool.name
            except ConflictError:
                pass  # Expected behaviour
        finally:
            if subscription is not None:
                try:
                    await async_client.unsubscribe(subscription.id)
                except Exception:
                    pass

    async def test_unsubscribe_unknown_id_raises(
        self, async_client: AsyncTeardropClient
    ) -> None:
        """Unsubscribing from a non-existent subscription ID raises NotFoundError."""
        with pytest.raises(NotFoundError):
            await async_client.unsubscribe("nonexistent-subscription-000000")

    async def test_subscribe_invalid_tool_name(
        self, async_client: AsyncTeardropClient
    ) -> None:
        """Subscribing to a malformed tool name raises ValidationError or NotFoundError."""
        with pytest.raises((ValidationError, NotFoundError)):
            await async_client.subscribe("bad:::tool///name!!!")
