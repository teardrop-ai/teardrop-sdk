"""Tests for AsyncTeardropClient wallet endpoint methods."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from teardrop.client import AsyncTeardropClient
from teardrop.exceptions import NotFoundError
from teardrop.models import AgentWallet, LinkWalletRequest, Wallet

from .conftest import _json_response


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


_WALLET = {
    "id": "w-1",
    "org_id": "org-1",
    "user_id": "user-1",
    "address": "0xABCD",
    "chain_id": 8453,
    "is_primary": True,
    "created_at": "2026-01-01T00:00:00Z",
}

_AGENT_WALLET = {
    "id": "aw-1",
    "org_id": "org-1",
    "address": "0xDEAD",
    "network": "base-sepolia",
    "is_active": True,
    "created_at": "2026-01-01T00:00:00Z",
}


# ─── link_wallet ─────────────────────────────────────────────────────────────


class TestLinkWallet:
    async def test_returns_wallet(self, client, mock_http):
        mock_http.post.return_value = _json_response(_WALLET)
        req = LinkWalletRequest(siwe_message="msg", siwe_signature="sig")
        result = await client.link_wallet(req)
        assert isinstance(result, Wallet)
        assert result.address == "0xABCD"

    async def test_request_fields_in_body(self, client, mock_http):
        mock_http.post.return_value = _json_response(_WALLET)
        req = LinkWalletRequest(siwe_message="my-msg", siwe_signature="my-sig")
        await client.link_wallet(req)
        _, kwargs = mock_http.post.call_args
        assert kwargs["json"]["siwe_message"] == "my-msg"
        assert kwargs["json"]["siwe_signature"] == "my-sig"

    async def test_correct_url(self, client, mock_http):
        mock_http.post.return_value = _json_response(_WALLET)
        await client.link_wallet(LinkWalletRequest(siwe_message="m", siwe_signature="s"))
        args, _ = mock_http.post.call_args
        assert args[0] == "http://test/wallets/link"


# ─── delete_wallet ───────────────────────────────────────────────────────────


class TestDeleteWallet:
    async def test_returns_none(self, client, mock_http):
        mock_http.delete.return_value = _json_response({}, status=204)
        result = await client.delete_wallet("w-1")
        assert result is None

    async def test_correct_url(self, client, mock_http):
        mock_http.delete.return_value = _json_response({}, status=204)
        await client.delete_wallet("w-abc")
        args, _ = mock_http.delete.call_args
        assert args[0] == "http://test/wallets/w-abc"

    async def test_404_raises_not_found(self, client, mock_http):
        mock_http.delete.return_value = _json_response({"detail": "Not found"}, status=404)
        with pytest.raises(NotFoundError):
            await client.delete_wallet("w-missing")


# ─── provision_agent_wallet ───────────────────────────────────────────────────


class TestProvisionAgentWallet:
    async def test_returns_agent_wallet(self, client, mock_http):
        mock_http.post.return_value = _json_response(_AGENT_WALLET)
        result = await client.provision_agent_wallet()
        assert isinstance(result, AgentWallet)
        assert result.network == "base-sepolia"
        assert result.address == "0xDEAD"

    async def test_correct_url(self, client, mock_http):
        mock_http.post.return_value = _json_response(_AGENT_WALLET)
        await client.provision_agent_wallet()
        args, _ = mock_http.post.call_args
        assert args[0] == "http://test/wallets/agent"


# ─── get_agent_wallet ─────────────────────────────────────────────────────────


class TestGetAgentWallet:
    async def test_no_include_balance_by_default(self, client, mock_http):
        mock_http.get.return_value = _json_response(_AGENT_WALLET)
        await client.get_agent_wallet()
        _, kwargs = mock_http.get.call_args
        # params should be empty dict — no include_balance sent
        assert kwargs.get("params", {}) == {}

    async def test_with_include_balance_passes_param(self, client, mock_http):
        mock_http.get.return_value = _json_response(_AGENT_WALLET)
        await client.get_agent_wallet(include_balance=True)
        _, kwargs = mock_http.get.call_args
        assert kwargs["params"] == {"include_balance": "true"}

    async def test_returns_agent_wallet(self, client, mock_http):
        mock_http.get.return_value = _json_response(_AGENT_WALLET)
        result = await client.get_agent_wallet()
        assert isinstance(result, AgentWallet)
        assert result.id == "aw-1"

    async def test_404_raises_not_found(self, client, mock_http):
        mock_http.get.return_value = _json_response({"detail": "Not found"}, status=404)
        with pytest.raises(NotFoundError):
            await client.get_agent_wallet()


# ─── deactivate_agent_wallet ──────────────────────────────────────────────────


class TestDeactivateAgentWallet:
    async def test_returns_none(self, client, mock_http):
        mock_http.delete.return_value = _json_response({}, status=204)
        result = await client.deactivate_agent_wallet()
        assert result is None

    async def test_correct_url(self, client, mock_http):
        mock_http.delete.return_value = _json_response({}, status=204)
        await client.deactivate_agent_wallet()
        args, _ = mock_http.delete.call_args
        assert args[0] == "http://test/wallets/agent"
