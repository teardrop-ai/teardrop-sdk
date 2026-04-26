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

import pytest

from teardrop.client import AsyncTeardropClient

_REQUIRED = ("TEARDROP_TEST_URL", "TEARDROP_TEST_EMAIL", "TEARDROP_TEST_SECRET")


def _missing() -> list[str]:
    return [v for v in _REQUIRED if not os.getenv(v)]


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
    return os.environ["TEARDROP_TEST_URL"].rstrip("/")


@pytest.fixture(scope="session")
async def async_client(integration_url: str) -> AsyncTeardropClient:  # type: ignore[misc]
    """A real AsyncTeardropClient authenticated against the test environment."""
    client = AsyncTeardropClient(
        integration_url,
        email=os.environ["TEARDROP_TEST_EMAIL"],
        secret=os.environ["TEARDROP_TEST_SECRET"],
    )
    yield client
    await client.close()
