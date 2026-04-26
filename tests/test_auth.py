"""Tests for teardrop.auth — TokenManager."""

from __future__ import annotations

import base64
import json
import time
from unittest.mock import AsyncMock, patch

import anyio
import pytest

from teardrop.auth import TokenManager
from teardrop.exceptions import AuthenticationError


def _make_jwt(exp: float | None = None, extra: dict | None = None) -> str:
    """Build a minimal unsigned JWT for testing."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=")
    payload_dict = extra or {}
    if exp is not None:
        payload_dict["exp"] = exp
    payload = base64.urlsafe_b64encode(json.dumps(payload_dict).encode()).rstrip(b"=")
    return f"{header.decode()}.{payload.decode()}.sig"


class _FakeHTTPResponse:
    """Mimics httpx.Response for simple POST mock."""

    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body

    @property
    def text(self):
        return json.dumps(self._body)


class _FakeClient:
    """Mimics httpx.AsyncClient with a mocked post()."""

    def __init__(self, response: _FakeHTTPResponse):
        self._response = response

    async def post(self, url: str, json: dict | None = None) -> _FakeHTTPResponse:
        return self._response


class TestReadExp:
    def test_valid_jwt(self):
        token = _make_jwt(exp=9999999999.0)
        assert TokenManager._read_exp(token) == 9999999999.0

    def test_missing_exp(self):
        token = _make_jwt(extra={"sub": "user"})
        assert TokenManager._read_exp(token) == 0.0

    def test_garbage_token(self):
        assert TokenManager._read_exp("not-a-jwt") == 0.0

    def test_empty_string(self):
        assert TokenManager._read_exp("") == 0.0


class TestCanRefresh:
    def test_email_secret(self):
        tm = TokenManager("http://x", email="a", secret="s")
        assert tm.can_refresh is True

    def test_client_credentials(self):
        tm = TokenManager("http://x", client_id="id", client_secret="sec")
        assert tm.can_refresh is True

    def test_static_token_no_refresh(self):
        tm = TokenManager("http://x", token="tok.en.sig")
        assert tm.can_refresh is False

    def test_no_credentials(self):
        tm = TokenManager("http://x")
        assert tm.can_refresh is False


class TestGetToken:
    @pytest.mark.asyncio
    async def test_returns_cached_token_when_fresh(self):
        future_exp = time.time() + 3600
        token = _make_jwt(exp=future_exp)
        tm = TokenManager("http://x", token=token)

        result = await tm.get_token(None)  # No client needed, token is fresh
        assert result == token

    @pytest.mark.asyncio
    async def test_refreshes_expired_token(self):
        past_exp = time.time() - 100
        old_token = _make_jwt(exp=past_exp)
        new_token = _make_jwt(exp=time.time() + 3600)

        tm = TokenManager("http://x", email="e", secret="s", token=old_token)

        client = _FakeClient(
            _FakeHTTPResponse(
                200, {"access_token": new_token, "token_type": "bearer", "expires_in": 3600}
            )
        )
        result = await tm.get_token(client)
        assert result == new_token

    @pytest.mark.asyncio
    async def test_static_token_returned_even_when_expired(self):
        """Static tokens (no credentials) should be returned as-is."""
        past_exp = time.time() - 100
        token = _make_jwt(exp=past_exp)
        tm = TokenManager("http://x", token=token)

        result = await tm.get_token(None)
        assert result == token

    @pytest.mark.asyncio
    async def test_no_token_no_credentials_raises(self):
        tm = TokenManager("http://x")
        with pytest.raises(AuthenticationError, match="No credentials"):
            await tm.get_token(None)

    @pytest.mark.asyncio
    async def test_token_request_failure_raises(self):
        tm = TokenManager("http://x", email="e", secret="s")
        client = _FakeClient(_FakeHTTPResponse(401, {"detail": "bad creds"}))
        with pytest.raises(AuthenticationError, match="401"):
            await tm.get_token(client)


class TestFetchTokenClientCredentials:
    @pytest.mark.asyncio
    async def test_client_credentials_path(self):
        """_fetch_token should send client_id/client_secret when those are set."""
        import time as _time
        new_token = _make_jwt(exp=_time.time() + 3600)
        client = _FakeClient(
            _FakeHTTPResponse(
                200, {"access_token": new_token, "token_type": "bearer", "expires_in": 3600}
            )
        )
        tm = TokenManager("http://x", client_id="cid", client_secret="csec")
        # Expire the (non-existent) token so a fetch is triggered
        tm._expires_at = 0.0
        result = await tm.get_token(client)
        assert result == new_token

    @pytest.mark.asyncio
    async def test_refresh_token_stored_when_present(self):
        """When the token response contains a refresh_token it must be stored."""
        import time as _time
        new_token = _make_jwt(exp=_time.time() + 3600)
        client = _FakeClient(
            _FakeHTTPResponse(
                200,
                {
                    "access_token": new_token,
                    "token_type": "bearer",
                    "expires_in": 3600,
                    "refresh_token": "rt-fresh",
                },
            )
        )
        tm = TokenManager("http://x", email="e", secret="s")
        await tm.get_token(client)
        assert tm._refresh_token == "rt-fresh"


class TestAuthenticateSIWE:
    @pytest.mark.asyncio
    async def test_success(self):
        token = _make_jwt(exp=time.time() + 3600)
        client = _FakeClient(
            _FakeHTTPResponse(
                200, {"access_token": token, "token_type": "bearer", "expires_in": 3600}
            )
        )
        tm = TokenManager("http://x")
        result = await tm.authenticate_siwe(client, "siwe-msg", "0xSIG")
        assert result == token

    @pytest.mark.asyncio
    async def test_failure(self):
        client = _FakeClient(_FakeHTTPResponse(401, {"detail": "invalid sig"}))
        tm = TokenManager("http://x")
        with pytest.raises(AuthenticationError):
            await tm.authenticate_siwe(client, "bad", "bad")


class TestGetTokenConcurrency:
    """Verify that concurrent calls with an expired token fire _fetch_token exactly once."""

    @pytest.mark.asyncio
    async def test_concurrent_refresh_calls_fetch_once(self):
        """10 concurrent get_token() calls on an expired token must call _fetch_token once."""
        import time as _time

        new_token = _make_jwt(exp=_time.time() + 3600)
        response = _FakeHTTPResponse(
            200, {"access_token": new_token, "token_type": "bearer", "expires_in": 3600}
        )

        tm = TokenManager("http://x", email="e", secret="s")
        tm._expires_at = 0.0  # force token as expired

        fetch_mock = AsyncMock(return_value=new_token)

        async def run_concurrently() -> None:
            async with anyio.create_task_group() as tg:
                for _ in range(10):
                    tg.start_soon(tm.get_token, _FakeClient(response))

        with patch.object(tm, "_fetch_token", fetch_mock):
            await run_concurrently()

        fetch_mock.assert_called_once()
