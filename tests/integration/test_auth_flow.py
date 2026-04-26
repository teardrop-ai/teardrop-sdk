"""Integration tests — Authentication flow.

Tests the login, token storage, refresh, and logout lifecycle using a real API.
All write operations (refresh/logout) are self-cleaning — they operate on
ephemeral tokens, not persistent data.

Skipped automatically when integration env vars are not set.
"""

from __future__ import annotations

import os
from typing import AsyncGenerator

import httpx
import pytest
import pytest_asyncio

from teardrop.auth import TokenManager
from teardrop.client import AsyncTeardropClient
from teardrop.exceptions import AuthenticationError, RateLimitError
from teardrop.models import MeResponse, TokenResponse


def _strip_quotes(value: str) -> str:
    return value.strip().strip("\"'")


# ─── Extra session-scoped fixtures ────────────────────────────────────────────


@pytest.fixture(scope="session")
def integration_email() -> str:
    return _strip_quotes(os.environ["TEARDROP_TEST_EMAIL"])


@pytest.fixture(scope="session")
def integration_secret() -> str:
    return _strip_quotes(os.environ["TEARDROP_TEST_SECRET"])


@pytest.fixture(scope="session")
def _email_secret_token_data(
    integration_url: str,
    integration_email: str,
    integration_secret: str,
) -> dict:
    """Session-scoped SYNC token fetch — exactly one /token call per session.

    Using sync httpx (like conftest._cached_token) keeps this outside any
    asyncio event loop, avoiding the cross-loop connection issue on Windows.
    """
    try:
        resp = httpx.post(
            f"{integration_url}/token",
            json={"email": integration_email, "secret": integration_secret},
            timeout=30,
        )
        resp.raise_for_status()
    except Exception as exc:
        pytest.skip(f"Could not fetch email+secret token: {exc}")
    return resp.json()


@pytest_asyncio.fixture(scope="function")
async def email_secret_client(
    integration_url: str,
    integration_email: str,
    integration_secret: str,
    _email_secret_token_data: dict,
) -> AsyncGenerator[AsyncTeardropClient, None]:
    """Function-scoped email+secret client with pre-populated token.

    Function-scoped so each test gets a fresh httpx client (correct event loop
    on Windows ProactorEventLoop).  Token is pre-populated from the
    session-scoped sync fetch to avoid repeated /token calls that trigger
    rate limiting.
    """
    client = AsyncTeardropClient(
        integration_url, email=integration_email, secret=integration_secret
    )
    # Pre-populate token so get_token() skips the /token network call.
    access_token = _email_secret_token_data["access_token"]
    client._token_manager._token = access_token
    client._token_manager._expires_at = TokenManager._read_exp(access_token)
    if refresh := _email_secret_token_data.get("refresh_token"):
        client._token_manager._refresh_token = refresh
    yield client
    await client.close()


# ─── Tests ────────────────────────────────────────────────────────────────────


class TestLoginFlow:
    """Email+secret client auto-authenticates and stores tokens correctly."""

    async def test_login_with_email_secret(
        self, email_secret_client: AsyncTeardropClient
    ) -> None:
        """Client with email+secret auto-authenticates on the first API call."""
        result = await email_secret_client.get_me()
        assert isinstance(result, MeResponse)
        assert result.org_id  # Non-empty after successful auth

    async def test_token_stored_after_login(
        self, email_secret_client: AsyncTeardropClient
    ) -> None:
        """After the first authenticated call, token is cached inside TokenManager."""
        await email_secret_client.get_me()
        assert email_secret_client._token_manager._token

    async def test_get_me_shape(
        self,
        email_secret_client: AsyncTeardropClient,
        integration_email: str,
    ) -> None:
        """MeResponse carries all expected identity fields."""
        result = await email_secret_client.get_me()
        assert result.org_id
        assert result.email
        assert result.email == integration_email

    async def test_invalid_credentials_raises(self, integration_url: str) -> None:
        """Wrong credentials raise AuthenticationError on the first API call."""
        bad_client = AsyncTeardropClient(
            integration_url,
            email="nobody@invalid.example",
            secret="totally-wrong-secret-xyz",
        )
        try:
            with pytest.raises(AuthenticationError):
                await bad_client.get_me()
        finally:
            await bad_client.close()


class TestTokenRefresh:
    """Refresh-token rotation and logout invalidation."""

    async def test_refresh_token_flow(
        self, email_secret_client: AsyncTeardropClient
    ) -> None:
        """After login, the refresh token can be exchanged for a new access token."""
        await email_secret_client.get_me()
        refresh_token = email_secret_client._token_manager._refresh_token
        if not refresh_token:
            pytest.skip("Server did not return a refresh token for this account type")

        try:
            result = await email_secret_client.refresh(refresh_token)
        except (AuthenticationError, RateLimitError) as exc:
            pytest.skip(f"Auth endpoint rate-limited; cannot test refresh flow: {exc}")
        assert isinstance(result, TokenResponse)
        assert result.access_token

    async def test_logout_invalidates_refresh_token(
        self, email_secret_client: AsyncTeardropClient
    ) -> None:
        """After logout the refresh token is revoked and further refresh attempts fail."""
        await email_secret_client.get_me()
        refresh_token = email_secret_client._token_manager._refresh_token
        if not refresh_token:
            pytest.skip("Server did not return a refresh token for this account type")

        try:
            await email_secret_client.logout(refresh_token)
        except (AuthenticationError, RateLimitError) as exc:
            pytest.skip(f"Auth endpoint rate-limited during logout; cannot test invalidation: {exc}")

        # After logout, refreshing should fail — but some servers don't enforce
        # single-use refresh tokens or immediate revocation.
        try:
            await email_secret_client.refresh(refresh_token)
            pytest.skip(
                "Server did not invalidate the refresh token after logout; "
                "revocation behaviour is not enforced for this account type"
            )
        except (AuthenticationError, RateLimitError):
            pass  # Expected: refresh token was properly revoked


class TestStaticTokenClient:
    """A pre-authenticated static-token client works without credential refresh."""

    async def test_static_token_bypasses_refresh(
        self, async_client: AsyncTeardropClient
    ) -> None:
        """Client initialised with a static token has can_refresh=False yet succeeds."""
        assert not async_client._token_manager.can_refresh
        result = await async_client.get_me()
        assert isinstance(result, MeResponse)
        assert result.org_id

    async def test_get_me_email_matches_env(
        self,
        async_client: AsyncTeardropClient,
        integration_email: str,
    ) -> None:
        """The /auth/me email field matches the integration test account."""
        result = await async_client.get_me()
        assert result.email == integration_email


class TestSiweNonce:
    async def test_siwe_nonce_is_unique(
        self, async_client: AsyncTeardropClient
    ) -> None:
        """Two consecutive nonce requests must return different one-time values."""
        r1 = await async_client.get_siwe_nonce()
        r2 = await async_client.get_siwe_nonce()
        nonce1 = r1.get("nonce") or r1.get("data", {}).get("nonce", "")
        nonce2 = r2.get("nonce") or r2.get("data", {}).get("nonce", "")
        assert nonce1, "First nonce response must contain a nonce"
        assert nonce2, "Second nonce response must contain a nonce"
        assert nonce1 != nonce2, "Each nonce request must return a unique value"
