"""Tests for AsyncTeardropClient custom tool methods."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from teardrop.client import AsyncTeardropClient
from teardrop.exceptions import APIError
from teardrop.models import CreateCustomToolRequest, CustomTool


def _json_response(
    body: dict | list, status: int = 200, headers: dict | None = None
) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        content=json.dumps(body).encode(),
        headers={"content-type": "application/json", **(headers or {})},
        request=httpx.Request("GET", "http://test"),
    )


_TOOL = {
    "id": "tool-123",
    "org_id": "org-abc",
    "name": "my_tool",
    "description": "Does a thing",
    "input_schema": {"type": "object", "properties": {}, "required": []},
    "webhook_url": "https://example.com/hook",
    "webhook_method": "POST",
    "has_auth": False,
    "timeout_seconds": 10,
    "is_active": True,
    "created_at": None,
    "updated_at": None,
}


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


class TestCreateTool:
    @pytest.mark.asyncio
    async def test_returns_custom_tool(self, client, mock_http):
        mock_http.post = AsyncMock(return_value=_json_response(_TOOL))
        req = CreateCustomToolRequest(
            name="my_tool",
            description="Does a thing",
            input_schema={"type": "object", "properties": {}, "required": []},
            webhook_url="https://example.com/hook",
        )
        result = await client.create_tool(req)
        assert isinstance(result, CustomTool)
        assert result.id == "tool-123"

    @pytest.mark.asyncio
    async def test_excludes_none_fields(self, client, mock_http):
        mock_http.post = AsyncMock(return_value=_json_response(_TOOL))
        req = CreateCustomToolRequest(
            name="my_tool",
            description="Does a thing",
            input_schema={},
            webhook_url="https://example.com/hook",
            auth_header_name=None,
        )
        await client.create_tool(req)
        call_kwargs = mock_http.post.call_args.kwargs
        assert "auth_header_name" not in call_kwargs["json"]

    @pytest.mark.asyncio
    async def test_propagates_api_error(self, client, mock_http):
        mock_http.post = AsyncMock(
            return_value=_json_response({"detail": "Limit reached"}, status=422)
        )
        req = CreateCustomToolRequest(
            name="t", description="d", input_schema={}, webhook_url="https://example.com"
        )
        with pytest.raises(APIError):
            await client.create_tool(req)


class TestListTools:
    @pytest.mark.asyncio
    async def test_returns_list(self, client, mock_http):
        mock_http.get = AsyncMock(return_value=_json_response([_TOOL, _TOOL]))
        result = await client.list_tools()
        assert len(result) == 2
        assert all(isinstance(t, CustomTool) for t in result)

    @pytest.mark.asyncio
    async def test_empty_list(self, client, mock_http):
        mock_http.get = AsyncMock(return_value=_json_response([]))
        result = await client.list_tools()
        assert result == []


class TestGetTool:
    @pytest.mark.asyncio
    async def test_returns_tool(self, client, mock_http):
        mock_http.get = AsyncMock(return_value=_json_response(_TOOL))
        result = await client.get_tool("tool-123")
        assert isinstance(result, CustomTool)
        assert result.id == "tool-123"

    @pytest.mark.asyncio
    async def test_404_raises_api_error(self, client, mock_http):
        mock_http.get = AsyncMock(
            return_value=_json_response({"detail": "Not found"}, status=404)
        )
        with pytest.raises(APIError):
            await client.get_tool("missing")


class TestUpdateTool:
    @pytest.mark.asyncio
    async def test_returns_updated_tool(self, client, mock_http):
        updated = {**_TOOL, "is_active": False}
        mock_http.patch = AsyncMock(return_value=_json_response(updated))
        result = await client.update_tool("tool-123", is_active=False)
        assert isinstance(result, CustomTool)
        assert result.is_active is False

    @pytest.mark.asyncio
    async def test_passes_fields_as_json(self, client, mock_http):
        mock_http.patch = AsyncMock(return_value=_json_response(_TOOL))
        await client.update_tool("tool-123", timeout_seconds=20)
        call_kwargs = mock_http.patch.call_args.kwargs
        assert call_kwargs["json"] == {"timeout_seconds": 20}


class TestDeleteTool:
    @pytest.mark.asyncio
    async def test_returns_none_on_204(self, client, mock_http):
        mock_http.delete = AsyncMock(
            return_value=httpx.Response(
                status_code=204,
                content=b"",
                request=httpx.Request("DELETE", "http://test"),
            )
        )
        result = await client.delete_tool("tool-123")
        assert result is None

    @pytest.mark.asyncio
    async def test_404_raises_api_error(self, client, mock_http):
        mock_http.delete = AsyncMock(
            return_value=_json_response({"detail": "Not found"}, status=404)
        )
        with pytest.raises(APIError):
            await client.delete_tool("missing")
