"""Tests for AsyncTeardropClient auth endpoint methods."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from teardrop.client import AsyncTeardropClient
from teardrop.exceptions import AuthenticationError, ConflictError, ValidationError
from teardrop.models import TokenResponse

from .conftest import _json_response, _make_jwt


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    return AsyncTeardropClient("http://test", token="tok.en.sig")


@pytest.fixture
def mock_http(client):
    mock = AsyncMock()
    mock.is_closed = False
    client._http = mock
    with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
        yield mock


def _token_response_dict() -> dict:
    """Build a valid TokenResponse payload using a real decodable JWT."""
    return {
        "access_token": _make_jwt(exp=9999999999.0),
        "token_type": "bearer",
        "expires_in": 3600,
        "refresh_token": "rt-abc",
    }


# ─── get_siwe_nonce ───────────────────────────────────────────────────────────


class TestGetSiweNonce:
    async def test_returns_dict_with_nonce(self, client, mock_http):
        mock_http.get.return_value = _json_response({"nonce": "abc123"})
        result = await client.get_siwe_nonce()
        assert result == {"nonce": "abc123"}
        mock_http.get.assert_called_once_with("http://test/auth/siwe/nonce")

    async def test_401_raises_auth_error(self, client, mock_http):
        mock_http.get.return_value = _json_response({"detail": "Unauthorized"}, status=401)
        with pytest.raises(AuthenticationError):
            await client.get_siwe_nonce()


# ─── authenticate_siwe (async) ────────────────────────────────────────────────


class TestAuthenticateSiweAsync:
    async def test_delegates_to_token_manager(self, client, mock_http):
        with patch.object(
            client._token_manager, "authenticate_siwe", return_value="new.tok.sig"
        ) as mock_auth:
            result = await client.authenticate_siwe("msg", "sig")
        assert result == "new.tok.sig"
        mock_auth.assert_called_once()


# ─── register ─────────────────────────────────────────────────────────────────


class TestRegister:
    async def test_returns_token_response(self, client, mock_http):
        mock_http.post.return_value = _json_response(_token_response_dict())
        result = await client.register(org_name="Acme", email="u@acme.com", password="s3cr3t")
        assert isinstance(result, TokenResponse)
        assert result.refresh_token == "rt-abc"

    async def test_stores_token_in_manager(self, client, mock_http):
        payload = _token_response_dict()
        mock_http.post.return_value = _json_response(payload)
        result = await client.register(org_name="Acme", email="u@acme.com", password="s3cr3t")
        assert client._token_manager._token == result.access_token
        assert client._token_manager._refresh_token == "rt-abc"
        assert client._token_manager._expires_at == 9999999999.0

    async def test_body_fields_sent(self, client, mock_http):
        mock_http.post.return_value = _json_response(_token_response_dict())
        await client.register(org_name="Acme", email="u@acme.com", password="s3cr3t")
        _, kwargs = mock_http.post.call_args
        body = kwargs["json"]
        assert body == {"org_name": "Acme", "email": "u@acme.com", "password": "s3cr3t"}

    async def test_409_raises_conflict(self, client, mock_http):
        mock_http.post.return_value = _json_response({"detail": "Org already exists"}, status=409)
        with pytest.raises(ConflictError):
            await client.register(org_name="Acme", email="u@acme.com", password="s3cr3t")


# ─── register_invite ──────────────────────────────────────────────────────────


class TestRegisterInvite:
    async def test_returns_token_response(self, client, mock_http):
        mock_http.post.return_value = _json_response(_token_response_dict())
        result = await client.register_invite(
            token="invite-tok", email="u@acme.com", password="s3cr3t"
        )
        assert isinstance(result, TokenResponse)

    async def test_stores_token_in_manager(self, client, mock_http):
        payload = _token_response_dict()
        mock_http.post.return_value = _json_response(payload)
        result = await client.register_invite(
            token="invite-tok", email="u@acme.com", password="s3cr3t"
        )
        assert client._token_manager._token == result.access_token
        assert client._token_manager._refresh_token == "rt-abc"

    async def test_422_raises_validation_error(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {"detail": "Invalid token"}, status=422
        )
        with pytest.raises(ValidationError):
            await client.register_invite(
                token="bad-tok", email="u@acme.com", password="s3cr3t"
            )


# ─── refresh ──────────────────────────────────────────────────────────────────


class TestRefresh:
    async def test_returns_token_response(self, client, mock_http):
        mock_http.post.return_value = _json_response(_token_response_dict())
        result = await client.refresh("old-refresh-token")
        assert isinstance(result, TokenResponse)

    async def test_rotates_token_in_manager(self, client, mock_http):
        payload = _token_response_dict()
        mock_http.post.return_value = _json_response(payload)
        result = await client.refresh("old-refresh-token")
        assert client._token_manager._token == result.access_token
        assert client._token_manager._refresh_token == "rt-abc"
        assert client._token_manager._expires_at == 9999999999.0

    async def test_refresh_token_in_body(self, client, mock_http):
        mock_http.post.return_value = _json_response(_token_response_dict())
        await client.refresh("my-refresh-token")
        _, kwargs = mock_http.post.call_args
        assert kwargs["json"] == {"refresh_token": "my-refresh-token"}


# ─── logout ───────────────────────────────────────────────────────────────────


class TestLogout:
    async def test_returns_none(self, client, mock_http):
        mock_http.post.return_value = _json_response({}, status=200)
        result = await client.logout("rt-abc")
        assert result is None

    async def test_posts_refresh_token(self, client, mock_http):
        mock_http.post.return_value = _json_response({})
        await client.logout("rt-abc")
        _, kwargs = mock_http.post.call_args
        assert kwargs["json"] == {"refresh_token": "rt-abc"}

    async def test_401_raises_auth_error(self, client, mock_http):
        mock_http.post.return_value = _json_response({"detail": "Unauthorized"}, status=401)
        with pytest.raises(AuthenticationError):
            await client.logout("bad-token")


# ─── verify_email ─────────────────────────────────────────────────────────────


class TestVerifyEmail:
    async def test_passes_token_as_query_param(self, client, mock_http):
        mock_http.get.return_value = _json_response({"message": "verified"})
        await client.verify_email("one-time-token")
        _, kwargs = mock_http.get.call_args
        assert kwargs["params"] == {"token": "one-time-token"}

    async def test_returns_dict(self, client, mock_http):
        mock_http.get.return_value = _json_response({"message": "verified"})
        result = await client.verify_email("tok")
        assert isinstance(result, dict)
        assert result["message"] == "verified"


# ─── resend_verification ──────────────────────────────────────────────────────


class TestResendVerification:
    async def test_posts_email(self, client, mock_http):
        mock_http.post.return_value = _json_response({"message": "sent"})
        await client.resend_verification("u@example.com")
        _, kwargs = mock_http.post.call_args
        assert kwargs["json"] == {"email": "u@example.com"}

    async def test_returns_dict(self, client, mock_http):
        mock_http.post.return_value = _json_response({"message": "sent"})
        result = await client.resend_verification("u@example.com")
        assert isinstance(result, dict)


# ─── invite ───────────────────────────────────────────────────────────────────


class TestInvite:
    async def test_with_email_includes_email_in_body(self, client, mock_http):
        mock_http.post.return_value = _json_response({"invite_url": "https://..."})
        await client.invite(email="u@acme.com", role="member")
        _, kwargs = mock_http.post.call_args
        assert "email" in kwargs["json"]
        assert kwargs["json"]["email"] == "u@acme.com"
        assert kwargs["json"]["role"] == "member"

    async def test_without_email_omits_email_from_body(self, client, mock_http):
        mock_http.post.return_value = _json_response({"invite_url": "https://..."})
        await client.invite(role="admin")
        _, kwargs = mock_http.post.call_args
        assert "email" not in kwargs["json"]
        assert kwargs["json"]["role"] == "admin"

    async def test_default_role_is_member(self, client, mock_http):
        mock_http.post.return_value = _json_response({"invite_url": "https://..."})
        await client.invite()
        _, kwargs = mock_http.post.call_args
        assert kwargs["json"]["role"] == "member"
