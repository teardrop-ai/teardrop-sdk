"""Tests for MCP server management methods (Obj 2.4 — Agent-as-MCP-Client)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from teardrop.client import AsyncTeardropClient
from teardrop.exceptions import (
    APIError,
    AuthenticationError,
    ConflictError,
    ForbiddenError,
    GatewayError,
    NotFoundError,
    ValidationError,
)
from teardrop.models import (
    CreateMcpServerRequest,
    DiscoverMcpToolsResponse,
    OrgMcpServer,
    UpdateMcpServerRequest,
)
from teardrop.streaming import parse_mcp_tool_name


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _json_response(
    body: dict | list, status: int = 200, headers: dict | None = None
) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        content=json.dumps(body).encode(),
        headers={"content-type": "application/json", **(headers or {})},
        request=httpx.Request("GET", "http://test"),
    )


_SERVER: dict = {
    "id": "srv-1",
    "org_id": "org-abc",
    "name": "my_server",
    "url": "https://mcp.example.com/sse",
    "auth_type": "none",
    "has_auth": False,
    "auth_header_name": None,
    "is_active": True,
    "timeout_seconds": 15,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}


@pytest.fixture
def client() -> AsyncTeardropClient:
    return AsyncTeardropClient("http://test", token="tok.en.sig")


@pytest.fixture
def mock_http(client: AsyncTeardropClient) -> AsyncMock:
    mock = AsyncMock()
    mock.is_closed = False
    client._http = mock
    with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
        yield mock


# ─── CreateMcpServer ──────────────────────────────────────────────────────────


class TestCreateMcpServer:
    @pytest.mark.asyncio
    async def test_create_success(self, client: AsyncTeardropClient, mock_http: AsyncMock) -> None:
        mock_http.post = AsyncMock(return_value=_json_response(_SERVER, status=201))
        req = CreateMcpServerRequest(name="my_server", url="https://mcp.example.com/sse")
        result = await client.create_mcp_server(req)
        assert isinstance(result, OrgMcpServer)
        assert result.name == "my_server"
        assert result.has_auth is False

    @pytest.mark.asyncio
    async def test_create_with_bearer_auth(
        self, client: AsyncTeardropClient, mock_http: AsyncMock
    ) -> None:
        server_with_auth = {**_SERVER, "name": "secure_srv", "has_auth": True, "auth_type": "bearer"}
        mock_http.post = AsyncMock(return_value=_json_response(server_with_auth, status=201))
        req = CreateMcpServerRequest(
            name="secure_srv",
            url="https://mcp.example.com/sse",
            auth_type="bearer",
            auth_token="secret",
        )
        result = await client.create_mcp_server(req)
        assert result.has_auth is True
        assert result.auth_type == "bearer"
        # auth_token is write-only — must never appear on the response model
        assert not hasattr(result, "auth_token")

    @pytest.mark.asyncio
    async def test_create_posts_to_correct_url(
        self, client: AsyncTeardropClient, mock_http: AsyncMock
    ) -> None:
        mock_http.post = AsyncMock(return_value=_json_response(_SERVER, status=201))
        req = CreateMcpServerRequest(name="my_server", url="https://mcp.example.com/sse")
        await client.create_mcp_server(req)
        url_called = mock_http.post.call_args.args[0]
        assert url_called == "http://test/mcp/servers"

    def test_pydantic_rejects_header_auth_missing_header_name(self) -> None:
        """SDK-side model_validator catches missing auth_header_name."""
        with pytest.raises(Exception):
            CreateMcpServerRequest(
                name="h",
                url="https://mcp.example.com/sse",
                auth_type="header",
                auth_token="x",
            )

    def test_pydantic_rejects_bearer_auth_missing_token(self) -> None:
        with pytest.raises(Exception):
            CreateMcpServerRequest(
                name="b",
                url="https://mcp.example.com/sse",
                auth_type="bearer",
            )

    @pytest.mark.asyncio
    async def test_name_collision_raises_conflict_error(
        self, client: AsyncTeardropClient, mock_http: AsyncMock
    ) -> None:
        mock_http.post = AsyncMock(
            return_value=_json_response({"detail": "name already exists"}, status=409)
        )
        req = CreateMcpServerRequest(name="my_server", url="https://mcp.example.com/sse")
        with pytest.raises(ConflictError) as exc_info:
            await client.create_mcp_server(req)
        assert "already exists" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_422_raises_validation_error(
        self, client: AsyncTeardropClient, mock_http: AsyncMock
    ) -> None:
        mock_http.post = AsyncMock(
            return_value=_json_response({"detail": "SSRF blocked"}, status=422)
        )
        req = CreateMcpServerRequest(name="my_server", url="https://mcp.example.com/sse")
        with pytest.raises(ValidationError):
            await client.create_mcp_server(req)

    @pytest.mark.asyncio
    async def test_conflict_is_subclass_of_api_error(
        self, client: AsyncTeardropClient, mock_http: AsyncMock
    ) -> None:
        """ConflictError inherits APIError — existing catch-all handlers still work."""
        mock_http.post = AsyncMock(
            return_value=_json_response({"detail": "conflict"}, status=409)
        )
        req = CreateMcpServerRequest(name="my_server", url="https://mcp.example.com/sse")
        with pytest.raises(APIError):
            await client.create_mcp_server(req)


# ─── ListMcpServers ───────────────────────────────────────────────────────────


class TestListMcpServers:
    @pytest.mark.asyncio
    async def test_list_empty(self, client: AsyncTeardropClient, mock_http: AsyncMock) -> None:
        mock_http.get = AsyncMock(return_value=_json_response([]))
        result = await client.list_mcp_servers()
        assert result == []

    @pytest.mark.asyncio
    async def test_list_returns_servers(
        self, client: AsyncTeardropClient, mock_http: AsyncMock
    ) -> None:
        mock_http.get = AsyncMock(return_value=_json_response([_SERVER, _SERVER]))
        result = await client.list_mcp_servers()
        assert len(result) == 2
        assert all(isinstance(s, OrgMcpServer) for s in result)

    @pytest.mark.asyncio
    async def test_requires_auth(self, client: AsyncTeardropClient, mock_http: AsyncMock) -> None:
        mock_http.get = AsyncMock(
            return_value=_json_response({"detail": "Unauthorized"}, status=401)
        )
        with pytest.raises(AuthenticationError):
            await client.list_mcp_servers()


# ─── GetMcpServer ─────────────────────────────────────────────────────────────


class TestGetMcpServer:
    @pytest.mark.asyncio
    async def test_get_returns_server(
        self, client: AsyncTeardropClient, mock_http: AsyncMock
    ) -> None:
        mock_http.get = AsyncMock(return_value=_json_response(_SERVER))
        result = await client.get_mcp_server("srv-1")
        assert isinstance(result, OrgMcpServer)
        assert result.id == "srv-1"

    @pytest.mark.asyncio
    async def test_get_not_found_raises_not_found_error(
        self, client: AsyncTeardropClient, mock_http: AsyncMock
    ) -> None:
        mock_http.get = AsyncMock(
            return_value=_json_response({"detail": "Not found"}, status=404)
        )
        with pytest.raises(NotFoundError):
            await client.get_mcp_server("nonexistent-id")

    @pytest.mark.asyncio
    async def test_not_found_is_subclass_of_api_error(
        self, client: AsyncTeardropClient, mock_http: AsyncMock
    ) -> None:
        mock_http.get = AsyncMock(
            return_value=_json_response({"detail": "Not found"}, status=404)
        )
        with pytest.raises(APIError):
            await client.get_mcp_server("nonexistent-id")


# ─── UpdateMcpServer ──────────────────────────────────────────────────────────


class TestUpdateMcpServer:
    @pytest.mark.asyncio
    async def test_patch_sends_only_set_fields(
        self, client: AsyncTeardropClient, mock_http: AsyncMock
    ) -> None:
        mock_http.patch = AsyncMock(
            return_value=_json_response({**_SERVER, "is_active": False})
        )
        req = UpdateMcpServerRequest(is_active=False)
        await client.update_mcp_server("srv-1", req)
        call_kwargs = mock_http.patch.call_args.kwargs
        assert call_kwargs["json"] == {"is_active": False}

    @pytest.mark.asyncio
    async def test_patch_clear_token_sends_explicit_null(
        self, client: AsyncTeardropClient, mock_http: AsyncMock
    ) -> None:
        mock_http.patch = AsyncMock(
            return_value=_json_response({**_SERVER, "has_auth": False})
        )
        req = UpdateMcpServerRequest(auth_token=None)
        result = await client.update_mcp_server("srv-1", req)
        call_kwargs = mock_http.patch.call_args.kwargs
        # Explicit None must be present in the payload to clear the stored token
        assert "auth_token" in call_kwargs["json"]
        assert call_kwargs["json"]["auth_token"] is None
        assert result.has_auth is False

    @pytest.mark.asyncio
    async def test_empty_request_reaches_server_returns_422(
        self, client: AsyncTeardropClient, mock_http: AsyncMock
    ) -> None:
        """No pre-validation on empty body — server enforces the constraint."""
        mock_http.patch = AsyncMock(
            return_value=_json_response({"detail": "no fields provided"}, status=422)
        )
        req = UpdateMcpServerRequest()
        with pytest.raises(ValidationError):
            await client.update_mcp_server("srv-1", req)

    @pytest.mark.asyncio
    async def test_patch_not_found(
        self, client: AsyncTeardropClient, mock_http: AsyncMock
    ) -> None:
        mock_http.patch = AsyncMock(
            return_value=_json_response({"detail": "Not found"}, status=404)
        )
        with pytest.raises(NotFoundError):
            await client.update_mcp_server("nonexistent-id", UpdateMcpServerRequest(is_active=True))


# ─── DeleteMcpServer ──────────────────────────────────────────────────────────


class TestDeleteMcpServer:
    @pytest.mark.asyncio
    async def test_delete_success_returns_status(
        self, client: AsyncTeardropClient, mock_http: AsyncMock
    ) -> None:
        mock_http.delete = AsyncMock(return_value=_json_response({"status": "deleted"}))
        result = await client.delete_mcp_server("srv-1")
        assert result == {"status": "deleted"}

    @pytest.mark.asyncio
    async def test_delete_not_found_raises_not_found_error(
        self, client: AsyncTeardropClient, mock_http: AsyncMock
    ) -> None:
        mock_http.delete = AsyncMock(
            return_value=_json_response({"detail": "Not found"}, status=404)
        )
        with pytest.raises(NotFoundError):
            await client.delete_mcp_server("nonexistent-id")

    @pytest.mark.asyncio
    async def test_delete_hits_correct_url(
        self, client: AsyncTeardropClient, mock_http: AsyncMock
    ) -> None:
        mock_http.delete = AsyncMock(return_value=_json_response({"status": "deleted"}))
        await client.delete_mcp_server("srv-1")
        url_called = mock_http.delete.call_args.args[0]
        assert url_called == "http://test/mcp/servers/srv-1"


# ─── DiscoverMcpServerTools ───────────────────────────────────────────────────


class TestDiscoverMcpServerTools:
    @pytest.mark.asyncio
    async def test_discover_returns_tools(
        self, client: AsyncTeardropClient, mock_http: AsyncMock
    ) -> None:
        body = {
            "server_id": "srv-1",
            "tools": [
                {
                    "name": "add",
                    "description": "Adds two numbers",
                    "input_schema": {"type": "object", "properties": {}},
                }
            ],
        }
        mock_http.post = AsyncMock(return_value=_json_response(body))
        result = await client.discover_mcp_server_tools("srv-1")
        assert isinstance(result, DiscoverMcpToolsResponse)
        assert result.server_id == "srv-1"
        assert len(result.tools) == 1
        assert result.tools[0].name == "add"

    @pytest.mark.asyncio
    async def test_discover_server_not_found(
        self, client: AsyncTeardropClient, mock_http: AsyncMock
    ) -> None:
        mock_http.post = AsyncMock(
            return_value=_json_response({"detail": "Not found"}, status=404)
        )
        with pytest.raises(NotFoundError):
            await client.discover_mcp_server_tools("nonexistent-id")

    @pytest.mark.asyncio
    async def test_discover_gateway_error_on_502(
        self, client: AsyncTeardropClient, mock_http: AsyncMock
    ) -> None:
        mock_http.post = AsyncMock(
            return_value=_json_response({"detail": "MCP server unreachable"}, status=502)
        )
        with pytest.raises(GatewayError) as exc_info:
            await client.discover_mcp_server_tools("srv-1")
        assert "unreachable" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_discover_posts_to_discover_endpoint(
        self, client: AsyncTeardropClient, mock_http: AsyncMock
    ) -> None:
        body = {"server_id": "srv-1", "tools": []}
        mock_http.post = AsyncMock(return_value=_json_response(body))
        await client.discover_mcp_server_tools("srv-1")
        url_called = mock_http.post.call_args.args[0]
        assert url_called == "http://test/mcp/servers/srv-1/discover"


# ─── AdminListMcpServers ──────────────────────────────────────────────────────


class TestAdminListMcpServers:
    @pytest.mark.asyncio
    async def test_admin_list_returns_active_and_inactive(
        self, client: AsyncTeardropClient, mock_http: AsyncMock
    ) -> None:
        inactive = {**_SERVER, "id": "srv-2", "is_active": False}
        mock_http.get = AsyncMock(return_value=_json_response([_SERVER, inactive]))
        result = await client.admin_list_mcp_servers("org-abc")
        assert len(result) == 2
        assert any(not s.is_active for s in result)

    @pytest.mark.asyncio
    async def test_admin_requires_admin_role(
        self, client: AsyncTeardropClient, mock_http: AsyncMock
    ) -> None:
        mock_http.get = AsyncMock(
            return_value=_json_response({"detail": "Forbidden"}, status=403)
        )
        with pytest.raises(ForbiddenError):
            await client.admin_list_mcp_servers("org-abc")

    @pytest.mark.asyncio
    async def test_admin_hits_admin_endpoint(
        self, client: AsyncTeardropClient, mock_http: AsyncMock
    ) -> None:
        mock_http.get = AsyncMock(return_value=_json_response([]))
        await client.admin_list_mcp_servers("org-abc")
        url_called = mock_http.get.call_args.args[0]
        assert url_called == "http://test/admin/mcp/servers/org-abc"


# ─── parse_mcp_tool_name ──────────────────────────────────────────────────────


class TestParseMcpToolName:
    def test_positive_match(self) -> None:
        result = parse_mcp_tool_name("my_server__web_search")
        assert result["is_mcp"] is True
        assert result["server"] == "my_server"  # type: ignore[typeddict-item]
        assert result["tool"] == "web_search"  # type: ignore[typeddict-item]

    def test_negative_match_no_separator(self) -> None:
        result = parse_mcp_tool_name("web_search")
        assert result["is_mcp"] is False

    def test_single_underscore_is_not_separator(self) -> None:
        result = parse_mcp_tool_name("web_search_v2")
        assert result["is_mcp"] is False

    def test_leading_double_underscore_is_not_mcp(self) -> None:
        """Separator must be preceded by at least one char (server name non-empty)."""
        result = parse_mcp_tool_name("__web_search")
        assert result["is_mcp"] is False

    def test_tool_name_with_underscore(self) -> None:
        result = parse_mcp_tool_name("my_server__add_two_numbers")
        assert result["is_mcp"] is True
        assert result["server"] == "my_server"  # type: ignore[typeddict-item]
        assert result["tool"] == "add_two_numbers"  # type: ignore[typeddict-item]

    def test_server_name_with_underscore(self) -> None:
        result = parse_mcp_tool_name("my_cool_server__do_thing")
        assert result["is_mcp"] is True
        assert result["server"] == "my_cool_server"  # type: ignore[typeddict-item]
        assert result["tool"] == "do_thing"  # type: ignore[typeddict-item]

    def test_uses_first_separator_only(self) -> None:
        """Multiple __ sequences: server is prefix before first occurrence."""
        result = parse_mcp_tool_name("srv__tool__extra")
        assert result["is_mcp"] is True
        assert result["server"] == "srv"  # type: ignore[typeddict-item]
        assert result["tool"] == "tool__extra"  # type: ignore[typeddict-item]
