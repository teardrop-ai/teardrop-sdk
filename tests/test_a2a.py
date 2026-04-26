"""Tests for AsyncTeardropClient A2A delegation and agent wallet methods."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from teardrop.client import AsyncTeardropClient
from teardrop.exceptions import NotFoundError
from teardrop.models import AddTrustedAgentRequest, TrustedAgent

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


_TRUSTED_AGENT = {
    "id": "ta-1",
    "org_id": "org-1",
    "agent_url": "https://agent.dev",
    "label": "My Agent",
    "max_cost_usdc": 0,
    "require_x402": False,
    "jwt_forward": False,
    "created_at": "2026-01-01T00:00:00Z",
}


# ─── add_trusted_agent ───────────────────────────────────────────────────────


class TestAddTrustedAgent:
    async def test_returns_trusted_agent(self, client, mock_http):
        mock_http.post.return_value = _json_response(_TRUSTED_AGENT)
        req = AddTrustedAgentRequest(agent_url="https://agent.dev", label="My Agent")
        result = await client.add_trusted_agent(req)
        assert isinstance(result, TrustedAgent)
        assert result.agent_url == "https://agent.dev"
        assert result.label == "My Agent"

    async def test_exclude_none_omits_unset_optional_fields(self, client, mock_http):
        mock_http.post.return_value = _json_response(_TRUSTED_AGENT)
        # label and max_cost_usdc are None / default — should be excluded from body
        req = AddTrustedAgentRequest(agent_url="https://agent.dev")
        await client.add_trusted_agent(req)
        _, kwargs = mock_http.post.call_args
        assert "label" not in kwargs["json"]

    async def test_optional_fields_included_when_set(self, client, mock_http):
        mock_http.post.return_value = _json_response(_TRUSTED_AGENT)
        req = AddTrustedAgentRequest(
            agent_url="https://agent.dev",
            label="myagent",
            max_cost_usdc=5000,
        )
        await client.add_trusted_agent(req)
        _, kwargs = mock_http.post.call_args
        assert kwargs["json"]["label"] == "myagent"
        assert kwargs["json"]["max_cost_usdc"] == 5000

    async def test_correct_url(self, client, mock_http):
        mock_http.post.return_value = _json_response(_TRUSTED_AGENT)
        await client.add_trusted_agent(AddTrustedAgentRequest(agent_url="https://a.dev"))
        args, _ = mock_http.post.call_args
        assert args[0] == "http://test/a2a/agents"


# ─── list_trusted_agents ─────────────────────────────────────────────────────


class TestListTrustedAgents:
    async def test_returns_list_of_trusted_agents(self, client, mock_http):
        mock_http.get.return_value = _json_response([_TRUSTED_AGENT, _TRUSTED_AGENT])
        result = await client.list_trusted_agents()
        assert len(result) == 2
        assert isinstance(result[0], TrustedAgent)

    async def test_empty_list(self, client, mock_http):
        mock_http.get.return_value = _json_response([])
        result = await client.list_trusted_agents()
        assert result == []


# ─── remove_trusted_agent ────────────────────────────────────────────────────


class TestRemoveTrustedAgent:
    async def test_returns_none(self, client, mock_http):
        mock_http.delete.return_value = _json_response({}, status=204)
        result = await client.remove_trusted_agent("ta-1")
        assert result is None

    async def test_correct_url(self, client, mock_http):
        mock_http.delete.return_value = _json_response({}, status=204)
        await client.remove_trusted_agent("ta-abc")
        args, _ = mock_http.delete.call_args
        assert args[0] == "http://test/a2a/agents/ta-abc"

    async def test_404_raises_not_found(self, client, mock_http):
        mock_http.delete.return_value = _json_response({"detail": "Not found"}, status=404)
        with pytest.raises(NotFoundError):
            await client.remove_trusted_agent("ta-missing")


# ─── get_delegations ─────────────────────────────────────────────────────────


class TestGetDelegations:
    async def test_returns_list_of_dicts(self, client, mock_http):
        mock_http.get.return_value = _json_response([{"id": "d-1"}, {"id": "d-2"}])
        result = await client.get_delegations()
        assert result == [{"id": "d-1"}, {"id": "d-2"}]

    async def test_limit_param_forwarded(self, client, mock_http):
        mock_http.get.return_value = _json_response([])
        await client.get_delegations(limit=5)
        _, kwargs = mock_http.get.call_args
        assert kwargs["params"] == {"limit": 5}

    async def test_correct_url(self, client, mock_http):
        mock_http.get.return_value = _json_response([])
        await client.get_delegations()
        args, _ = mock_http.get.call_args
        assert args[0] == "http://test/a2a/delegations"
