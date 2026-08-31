"""Tests for AsyncTeardropClient auth endpoint methods."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from teardrop.client import AsyncTeardropClient
from teardrop.exceptions import AuthenticationError, ConflictError, ValidationError
from teardrop.models import (
    PrincipalSpendLimitRequest,
    PrincipalSpendLimitResponse,
    ResendVerificationResponse,
    SiweNonceResponse,
    TokenResponse,
    VerifyEmailResponse,
    X402BootstrapResponse,
)

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


_VERIFY_RESPONSE = {"message": "verified", "verified": True}
_INVITE_RESPONSE = {
    "invite_url": "https://...",
    "token": "invite-token",
    "expires_at": "2026-01-02T00:00:00Z",
}


# ─── get_siwe_nonce ───────────────────────────────────────────────────────────


class TestGetSiweNonce:
    async def test_returns_nonce_response(self, client, mock_http):
        mock_http.get.return_value = _json_response({"nonce": "abc123"})
        result = await client.get_siwe_nonce()
        assert isinstance(result, SiweNonceResponse)
        assert result.nonce == "abc123"
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

    async def test_acquisition_source_sent_when_provided(self, client, mock_http):
        mock_http.post.return_value = _json_response(_token_response_dict())
        await client.register(
            org_name="Acme",
            email="u@acme.com",
            password="s3cr3t",
            acquisition_source="github",
        )
        _, kwargs = mock_http.post.call_args
        body = kwargs["json"]
        assert body["acquisition_source"] == "github"

    async def test_acquisition_source_omitted_when_none(self, client, mock_http):
        mock_http.post.return_value = _json_response(_token_response_dict())
        await client.register(org_name="Acme", email="u@acme.com", password="s3cr3t")
        _, kwargs = mock_http.post.call_args
        body = kwargs["json"]
        assert "acquisition_source" not in body

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

    async def test_acquisition_source_sent_when_provided(self, client, mock_http):
        mock_http.post.return_value = _json_response(_token_response_dict())
        await client.register_invite(
            token="invite-tok",
            email="u@acme.com",
            password="s3cr3t",
            acquisition_source="referral",
        )
        _, kwargs = mock_http.post.call_args
        body = kwargs["json"]
        assert body["acquisition_source"] == "referral"

    async def test_422_raises_validation_error(self, client, mock_http):
        mock_http.post.return_value = _json_response({"detail": "Invalid token"}, status=422)
        with pytest.raises(ValidationError):
            await client.register_invite(token="bad-tok", email="u@acme.com", password="s3cr3t")


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
        mock_http.get.return_value = _json_response(_VERIFY_RESPONSE)
        await client.verify_email("one-time-token")
        _, kwargs = mock_http.get.call_args
        assert kwargs["params"] == {"token": "one-time-token"}

    async def test_returns_verify_response(self, client, mock_http):
        mock_http.get.return_value = _json_response(_VERIFY_RESPONSE)
        result = await client.verify_email("tok")
        assert isinstance(result, VerifyEmailResponse)
        assert result.message == "verified"


# ─── resend_verification ──────────────────────────────────────────────────────


class TestResendVerification:
    async def test_posts_email(self, client, mock_http):
        mock_http.post.return_value = _json_response({"message": "sent"})
        await client.resend_verification("u@example.com")
        _, kwargs = mock_http.post.call_args
        assert kwargs["json"] == {"email": "u@example.com"}

    async def test_returns_resend_response(self, client, mock_http):
        mock_http.post.return_value = _json_response({"message": "sent"})
        result = await client.resend_verification("u@example.com")
        assert isinstance(result, ResendVerificationResponse)
        assert result.message == "sent"


# ─── invite ───────────────────────────────────────────────────────────────────


class TestInvite:
    async def test_with_email_includes_email_in_body(self, client, mock_http):
        mock_http.post.return_value = _json_response(_INVITE_RESPONSE)
        await client.invite(email="u@acme.com", role="member")
        _, kwargs = mock_http.post.call_args
        assert "email" in kwargs["json"]
        assert kwargs["json"]["email"] == "u@acme.com"
        assert kwargs["json"]["role"] == "member"

    async def test_without_email_omits_email_from_body(self, client, mock_http):
        mock_http.post.return_value = _json_response(_INVITE_RESPONSE)
        await client.invite(role="admin")
        _, kwargs = mock_http.post.call_args
        assert "email" not in kwargs["json"]
        assert kwargs["json"]["role"] == "admin"

    async def test_default_role_is_member(self, client, mock_http):
        mock_http.post.return_value = _json_response(_INVITE_RESPONSE)
        await client.invite()
        _, kwargs = mock_http.post.call_args
        assert kwargs["json"]["role"] == "member"


# ─── spend limits / x402 bootstrap (spec 1.6.0) ─────────────────────────────────


class TestOrgPrincipalSpendLimits:
    async def test_accepts_spec_bare_array_response(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            [
                {
                    "principal_id": "p-1",
                    "daily_limit_usdc": 1000,
                    "is_paused": False,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                }
            ]
        )
        result = await client.get_org_principal_spend_limits()
        assert result[0].principal_id == "p-1"

    async def test_returns_parsed_items(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {
                "items": [
                    {
                        "principal_id": "p-1",
                        "daily_limit_usdc": 1000,
                        "is_paused": False,
                        "created_at": "2026-01-01T00:00:00Z",
                        "updated_at": "2026-01-01T00:00:00Z",
                    }
                ]
            }
        )
        result = await client.get_org_principal_spend_limits()
        assert len(result) == 1
        assert isinstance(result[0], PrincipalSpendLimitResponse)
        assert result[0].daily_limit_usdc == 1000

    async def test_correct_url(self, client, mock_http):
        mock_http.get.return_value = _json_response({"items": []})
        await client.get_org_principal_spend_limits()
        args, _ = mock_http.get.call_args
        assert args[0] == "http://test/org/principals/spend-limits"


class TestSetOrgPrincipalSpendLimit:
    @pytest.mark.parametrize("daily_limit_usdc", [0, 100_000_001])
    def test_rejects_out_of_range_daily_limit(self, daily_limit_usdc):
        with pytest.raises(ValueError):
            PrincipalSpendLimitRequest(daily_limit_usdc=daily_limit_usdc)

    async def test_put_body_and_response(self, client, mock_http):
        mock_http.put.return_value = _json_response(
            {
                "principal_id": "p-1",
                "daily_limit_usdc": 2500,
                "is_paused": True,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-02T00:00:00Z",
            }
        )
        request = PrincipalSpendLimitRequest(daily_limit_usdc=2500, is_paused=True)
        result = await client.set_org_principal_spend_limit("p-1", request)
        assert isinstance(result, PrincipalSpendLimitResponse)
        args, kwargs = mock_http.put.call_args
        assert args[0] == "http://test/org/principals/p-1/spend-limit"
        assert kwargs["json"] == {"daily_limit_usdc": 2500, "is_paused": True}

    async def test_none_fields_excluded(self, client, mock_http):
        mock_http.put.return_value = _json_response(
            {
                "principal_id": "p-1",
                "daily_limit_usdc": 1,
                "is_paused": False,
                "created_at": "t",
                "updated_at": "t",
            }
        )
        await client.set_org_principal_spend_limit(
            "p-1", PrincipalSpendLimitRequest(daily_limit_usdc=1)
        )
        _, kwargs = mock_http.put.call_args
        assert kwargs["json"] == {"daily_limit_usdc": 1, "is_paused": False}

    async def test_quoted_principal_id(self, client, mock_http):
        mock_http.put.return_value = _json_response(
            {
                "principal_id": "p/1",
                "daily_limit_usdc": 1,
                "is_paused": False,
                "created_at": "t",
                "updated_at": "t",
            }
        )
        await client.set_org_principal_spend_limit(
            "p/1", PrincipalSpendLimitRequest(daily_limit_usdc=1)
        )
        args, _ = mock_http.put.call_args
        assert args[0] == "http://test/org/principals/p%2F1/spend-limit"


class TestDeleteOrgPrincipalSpendLimit:
    async def test_delete_returns_none(self, client, mock_http):
        mock_http.delete.return_value = _json_response({}, status=204)
        assert await client.delete_org_principal_spend_limit("p-1") is None
        args, _ = mock_http.delete.call_args
        assert args[0] == "http://test/org/principals/p-1/spend-limit"


class TestBootstrapX402:
    async def test_posts_grant_type_and_payment_header(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {
                "access_token": _make_jwt(exp=9999999999.0),
                "token_type": "bearer",
                "expires_in": 3600,
                "client_id": "cc-1",
                "org_id": "org-1",
                "client_secret": "one-time-secret",
            }
        )
        result = await client.bootstrap_x402("X-PAYMENT-HEADER-VALUE")
        assert isinstance(result, X402BootstrapResponse)
        assert result.client_secret == "one-time-secret"
        args, kwargs = mock_http.post.call_args
        assert args[0] == "http://test/token"
        assert kwargs["json"] == {"grant_type": "x402"}
        assert kwargs["headers"] == {"X-PAYMENT": "X-PAYMENT-HEADER-VALUE"}

    async def test_stores_access_token_in_manager(self, client, mock_http):
        access_token = _make_jwt(exp=9999999999.0)
        mock_http.post.return_value = _json_response(
            {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": 3600,
                "client_id": "cc-1",
                "org_id": "org-1",
            }
        )
        result = await client.bootstrap_x402("pay")
        assert client._token_manager._token == result.access_token
        assert client._token_manager._expires_at == 9999999999.0

    async def test_client_secret_optional(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {
                "access_token": _make_jwt(exp=9999999999.0),
                "token_type": "bearer",
                "expires_in": 3600,
                "client_id": "cc-1",
                "org_id": "org-1",
            }
        )
        result = await client.bootstrap_x402("pay")
        assert result.client_secret is None
