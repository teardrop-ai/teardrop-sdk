"""Tests for AsyncTeardropClient memory endpoint methods."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from teardrop.client import AsyncTeardropClient
from teardrop.exceptions import NotFoundError
from teardrop.models import MemoryEntry, StoreMemoryRequest

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


_MEMORY = {"id": "m-1", "content": "Remember this", "created_at": "2026-01-01T00:00:00Z"}


# ─── list_memories ────────────────────────────────────────────────────────────


class TestListMemories:
    async def test_returns_list_of_memory_entries(self, client, mock_http):
        mock_http.get.return_value = _json_response([_MEMORY, _MEMORY])
        result = await client.list_memories()
        assert len(result) == 2
        assert isinstance(result[0], MemoryEntry)
        assert result[0].content == "Remember this"

    async def test_limit_param_forwarded(self, client, mock_http):
        mock_http.get.return_value = _json_response([_MEMORY])
        await client.list_memories(limit=10)
        _, kwargs = mock_http.get.call_args
        assert kwargs["params"] == {"limit": 10}

    async def test_empty_list(self, client, mock_http):
        mock_http.get.return_value = _json_response([])
        result = await client.list_memories()
        assert result == []


# ─── create_memory ────────────────────────────────────────────────────────────


class TestCreateMemory:
    async def test_returns_memory_entry(self, client, mock_http):
        mock_http.post.return_value = _json_response(_MEMORY)
        req = StoreMemoryRequest(content="Remember this")
        result = await client.create_memory(req)
        assert isinstance(result, MemoryEntry)
        assert result.id == "m-1"
        assert result.content == "Remember this"

    async def test_content_in_body(self, client, mock_http):
        mock_http.post.return_value = _json_response(_MEMORY)
        req = StoreMemoryRequest(content="hello")
        await client.create_memory(req)
        _, kwargs = mock_http.post.call_args
        assert kwargs["json"]["content"] == "hello"

    async def test_correct_url(self, client, mock_http):
        mock_http.post.return_value = _json_response(_MEMORY)
        await client.create_memory(StoreMemoryRequest(content="x"))
        args, _ = mock_http.post.call_args
        assert args[0] == "http://test/memories"


# ─── delete_memory ────────────────────────────────────────────────────────────


class TestDeleteMemory:
    async def test_returns_none_on_204(self, client, mock_http):
        mock_http.delete.return_value = _json_response({}, status=204)
        result = await client.delete_memory("m-1")
        assert result is None

    async def test_correct_url(self, client, mock_http):
        mock_http.delete.return_value = _json_response({}, status=204)
        await client.delete_memory("m-abc")
        args, _ = mock_http.delete.call_args
        assert args[0] == "http://test/memories/m-abc"

    async def test_404_raises_not_found(self, client, mock_http):
        mock_http.delete.return_value = _json_response({"detail": "Not found"}, status=404)
        with pytest.raises(NotFoundError):
            await client.delete_memory("m-missing")
