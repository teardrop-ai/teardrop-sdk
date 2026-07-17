"""MCP server and tool-discovery models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

McpServerAuthType = Literal["none", "bearer", "header"]


class OrgMcpServer(BaseModel):
    """An external MCP server registered for an org."""

    id: str
    org_id: str
    name: str
    url: str
    auth_type: McpServerAuthType = "none"
    has_auth: bool = False
    auth_header_name: str | None = None
    is_active: bool = True
    timeout_seconds: int = 15
    created_at: str = ""
    updated_at: str = ""

    model_config = {"extra": "allow"}


McpServerResponse = OrgMcpServer


class McpServerDeletedResponse(BaseModel):
    """Response from DELETE /mcp/servers/{server_id}."""

    id: str
    deleted_at: str = ""

    model_config = {"extra": "allow"}


class CreateMcpServerRequest(BaseModel):
    """Request body for POST /mcp/servers."""

    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    url: str = Field(..., max_length=2048)
    auth_type: McpServerAuthType = "none"
    auth_token: str | None = None
    auth_header_name: str | None = Field(default=None, max_length=64)
    timeout_seconds: int = Field(default=15, ge=1, le=60)

    @model_validator(mode="after")
    def _check_auth_fields(self) -> "CreateMcpServerRequest":
        if self.auth_type != "none" and not self.auth_token:
            raise ValueError("auth_token is required when auth_type is not 'none'")
        if self.auth_type == "header" and not self.auth_header_name:
            raise ValueError("auth_header_name is required when auth_type is 'header'")
        return self


class UpdateMcpServerRequest(BaseModel):
    """Request body for PATCH /mcp/servers/{server_id}."""

    name: str | None = Field(default=None, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    url: str | None = Field(default=None, max_length=2048)
    auth_type: McpServerAuthType | None = None
    auth_token: str | None = None
    auth_header_name: str | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=60)
    is_active: bool | None = None


class McpToolDefinition(BaseModel):
    """A single tool schema as returned by POST /mcp/servers/{id}/discover."""

    name: str
    description: str
    input_schema: dict[str, Any]


class DiscoverMcpToolsResponse(BaseModel):
    """Response from POST /mcp/servers/{server_id}/discover."""

    server_id: str
    server_name: str = ""
    tools: list[McpToolDefinition]
    discovered_at: str = ""


McpDiscoverResponse = DiscoverMcpToolsResponse


class TestMcpToolResponse(BaseModel):
    """Response from POST /mcp/servers/{server_id}/test-tool."""

    success: bool
    output: dict[str, Any] = Field(default_factory=dict)
    error: str = ""

    model_config = {"extra": "allow"}
