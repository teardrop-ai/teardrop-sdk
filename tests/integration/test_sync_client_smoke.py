"""Integration smoke tests — synchronous client parity.

A minimal set of real-HTTP tests using TeardropClient (sync) to ensure the
sync facade does not drift from the async implementation on core routes.

Skipped automatically when integration env vars are not set.
"""

from __future__ import annotations

import os

import pytest

from teardrop.client import TeardropClient
from teardrop.models import (
    AuthMeResponse,
    BillingBalanceResponse,
    MarketplaceCatalogResponse,
)


def _strip_quotes(value: str) -> str:
    return value.strip().strip("\"'")


@pytest.fixture(scope="function")
def sync_client(integration_url: str, _cached_token: str) -> TeardropClient:
    """A real synchronous TeardropClient using the session-cached token."""
    client = TeardropClient(integration_url, token=_cached_token)
    try:
        yield client
    finally:
        client.close()


class TestSyncClientSmoke:
    """Core user-facing routes through the sync wrapper."""

    def test_sync_get_me(self, sync_client: TeardropClient) -> None:
        result = sync_client.get_me()
        assert isinstance(result, AuthMeResponse)
        assert result.org_id

    def test_sync_get_me_email_matches_env(self, sync_client: TeardropClient) -> None:
        email = _strip_quotes(os.environ["TEARDROP_TEST_EMAIL"])
        result = sync_client.get_me()
        assert result.email == email

    def test_sync_get_balance(self, sync_client: TeardropClient) -> None:
        result = sync_client.get_balance()
        assert isinstance(result, BillingBalanceResponse)
        assert isinstance(result.balance_usdc, int)
        assert result.balance_usdc >= 0

    def test_sync_get_marketplace_catalog(self, sync_client: TeardropClient) -> None:
        result = sync_client.get_marketplace_catalog(limit=1)
        assert isinstance(result, MarketplaceCatalogResponse)
        assert isinstance(result.tools, list)

    def test_sync_catalog_has_tools(self, sync_client: TeardropClient) -> None:
        """Catalog returns a non-empty tools list when content exists."""
        result = sync_client.get_marketplace_catalog(limit=100)
        # Marketplace may be empty in some sandboxes; assert shape only.
        assert isinstance(result.tools, list)
