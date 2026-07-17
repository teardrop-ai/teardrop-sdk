"""Tests for AsyncTeardropClient custom tool methods."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from teardrop.client import AsyncTeardropClient
from teardrop.exceptions import APIError

# Backward-compat aliases still importable
from teardrop.models import (
    CreateOrgToolRequest,
    OrgTool,
    ToolDeletedResponse,
    UpdateOrgToolRequest,
)


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
    "output_schema": None,
    "webhook_url": "https://example.com/hook",
    "webhook_method": "POST",
    "mcp_server_id": None,
    "mcp_tool_name": None,
    "has_auth": False,
    "timeout_seconds": 15,
    "is_active": True,
    "publish_as_mcp": False,
    "marketplace_description": "",
    "base_price_usdc": 0,
    "category": "",
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
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
    async def test_returns_org_tool(self, client, mock_http):
        mock_http.post = AsyncMock(return_value=_json_response(_TOOL))
        req = CreateOrgToolRequest(
            name="my_tool",
            description="Does a thing",
            input_schema={"type": "object", "properties": {}, "required": []},
            webhook_url="https://example.com/hook",
        )
        result = await client.create_tool(req)
        assert isinstance(result, OrgTool)
        assert result.id == "tool-123"

    @pytest.mark.asyncio
    async def test_excludes_none_fields(self, client, mock_http):
        mock_http.post = AsyncMock(return_value=_json_response(_TOOL))
        req = CreateOrgToolRequest(
            name="my_tool",
            description="Does a thing",
            input_schema={},
            webhook_url="https://example.com/hook",
            webhook_secret=None,
        )
        await client.create_tool(req)
        call_kwargs = mock_http.post.call_args.kwargs
        assert "webhook_secret" not in call_kwargs["json"]

    @pytest.mark.asyncio
    async def test_propagates_api_error(self, client, mock_http):
        mock_http.post = AsyncMock(
            return_value=_json_response({"detail": "Limit reached"}, status=422)
        )
        req = CreateOrgToolRequest(
            name="my_t", description="d", input_schema={}, webhook_url="https://example.com"
        )
        with pytest.raises(APIError):
            await client.create_tool(req)


class TestListTools:
    @pytest.mark.asyncio
    async def test_returns_list(self, client, mock_http):
        mock_http.get = AsyncMock(return_value=_json_response([_TOOL, _TOOL]))
        result = await client.list_tools()
        assert len(result) == 2
        assert all(isinstance(t, OrgTool) for t in result)

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
        assert isinstance(result, OrgTool)
        assert result.id == "tool-123"

    @pytest.mark.asyncio
    async def test_404_raises_api_error(self, client, mock_http):
        mock_http.get = AsyncMock(return_value=_json_response({"detail": "Not found"}, status=404))
        with pytest.raises(APIError):
            await client.get_tool("missing")


class TestUpdateTool:
    @pytest.mark.asyncio
    async def test_returns_updated_tool(self, client, mock_http):
        updated = {**_TOOL, "is_active": False}
        mock_http.patch = AsyncMock(return_value=_json_response(updated))
        result = await client.update_tool("tool-123", UpdateOrgToolRequest(is_active=False))
        assert isinstance(result, OrgTool)
        assert result.is_active is False

    @pytest.mark.asyncio
    async def test_passes_fields_as_json(self, client, mock_http):
        mock_http.patch = AsyncMock(return_value=_json_response(_TOOL))
        await client.update_tool("tool-123", UpdateOrgToolRequest(description="new desc"))
        call_kwargs = mock_http.patch.call_args.kwargs
        assert call_kwargs["json"] == {"description": "new desc"}


class TestDeleteTool:
    @pytest.mark.asyncio
    async def test_returns_deleted_response(self, client, mock_http):
        mock_http.delete = AsyncMock(
            return_value=_json_response(
                {"id": "tool-123", "status": "deleted", "deleted_at": "2026-01-01T00:00:00Z"}
            )
        )
        result = await client.delete_tool("tool-123")
        assert isinstance(result, ToolDeletedResponse)
        assert result.id == "tool-123"

    @pytest.mark.asyncio
    async def test_404_raises_api_error(self, client, mock_http):
        mock_http.delete = AsyncMock(
            return_value=_json_response({"detail": "Not found"}, status=404)
        )
        with pytest.raises(APIError):
            await client.delete_tool("missing")


class TestTestWebhook:
    @pytest.mark.asyncio
    async def test_returns_success_response(self, client, mock_http):
        from teardrop.models import TestWebhookRequest, TestWebhookResponse

        mock_http.post = AsyncMock(
            return_value=_json_response(
                {
                    "success": True,
                    "status_code": 200,
                    "latency_ms": 87,
                    "response_body": {"ok": True},
                    "error": None,
                }
            )
        )
        result = await client.test_webhook(
            TestWebhookRequest(webhook_url="https://example.com/hook", payload={"a": 1})
        )
        assert isinstance(result, TestWebhookResponse)
        assert result.success is True
        assert result.status_code == 200
        assert result.response_body == {"ok": True}

    @pytest.mark.asyncio
    async def test_posts_to_test_webhook_endpoint(self, client, mock_http):
        from teardrop.models import TestWebhookRequest

        mock_http.post = AsyncMock(
            return_value=_json_response(
                {
                    "success": False,
                    "status_code": None,
                    "latency_ms": 5,
                    "response_body": None,
                    "error": "connection refused",
                }
            )
        )
        await client.test_webhook(TestWebhookRequest(webhook_url="https://example.com/hook"))
        args, kwargs = mock_http.post.call_args
        assert args[0] == "http://test/tools/test-webhook"
        assert kwargs["json"]["webhook_url"] == "https://example.com/hook"

    @pytest.mark.asyncio
    async def test_422_raises_validation_error(self, client, mock_http):
        from teardrop.exceptions import ValidationError
        from teardrop.models import TestWebhookRequest

        mock_http.post = AsyncMock(
            return_value=_json_response({"detail": "Invalid URL"}, status=422)
        )
        with pytest.raises(ValidationError):
            await client.test_webhook(TestWebhookRequest(webhook_url="not-a-url"))
