"""Shared fixtures for integration tests.

Integration tests are only executed when the following environment variables
are set.  If any are missing every test in this directory is skipped cleanly.

    TEARDROP_TEST_URL     – base URL of the Teardrop API (e.g. https://api.teardrop.dev)
    TEARDROP_TEST_EMAIL   – email address of the test account
    TEARDROP_TEST_SECRET  – password / secret for the test account

In CI, set TEARDROP_TEST_URL as a repository variable and TEARDROP_TEST_EMAIL /
TEARDROP_TEST_SECRET as encrypted secrets.
"""

from __future__ import annotations

import os
from typing import AsyncGenerator

import httpx
import pytest
import pytest_asyncio

from teardrop.client import AsyncTeardropClient

_REQUIRED = ("TEARDROP_TEST_URL", "TEARDROP_TEST_EMAIL", "TEARDROP_TEST_SECRET")


def _missing() -> list[str]:
    return [v for v in _REQUIRED if not os.getenv(v)]


def _strip_quotes(value: str) -> str:
    return value.strip().strip("\"'")


@pytest.fixture(scope="session", autouse=True)
def require_integration_env():
    """Skip the entire session if integration credentials are not configured."""
    missing = _missing()
    if missing:
        pytest.skip(
            f"Integration tests skipped — set {', '.join(missing)} to enable",
            allow_module_level=True,
        )


@pytest.fixture(scope="session")
def integration_url() -> str:
    url = _strip_quotes(os.environ["TEARDROP_TEST_URL"]).rstrip("/")
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


@pytest.fixture(scope="session")
def _cached_token(integration_url: str) -> str:
    """Fetch one token synchronously for the whole session to avoid per-test 429."""
    resp = httpx.post(
        f"{integration_url}/token",
        json={
            "email": _strip_quotes(os.environ["TEARDROP_TEST_EMAIL"]),
            "secret": _strip_quotes(os.environ["TEARDROP_TEST_SECRET"]),
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


@pytest_asyncio.fixture(scope="function")
async def async_client(integration_url: str, _cached_token: str) -> AsyncGenerator[AsyncTeardropClient, None]:  # type: ignore[misc]
    """A real AsyncTeardropClient using the session-cached token."""
    client = AsyncTeardropClient(integration_url, token=_cached_token)
    yield client
    await client.close()
