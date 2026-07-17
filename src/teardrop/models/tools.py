"""Organization webhook tool models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateOrgToolRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(..., min_length=1, max_length=500)
    input_schema: dict[str, Any] = Field(...)
    webhook_url: str = Field(..., max_length=2048)
    webhook_method: str | None = None
    auth_header_name: str | None = None
    auth_header_value: str | None = None
    timeout_seconds: int | None = None
    publish_as_mcp: bool | None = None
    marketplace_description: str | None = None
    base_price_usdc: int | None = None


CreateCustomToolRequest = CreateOrgToolRequest


class UpdateOrgToolRequest(BaseModel):
    description: str | None = None
    input_schema: dict[str, Any] | None = None
    webhook_url: str | None = None
    webhook_method: str | None = None
    auth_header_name: str | None = None
    auth_header_value: str | None = None
    timeout_seconds: int | None = None
    is_active: bool | None = None
    publish_as_mcp: bool | None = None
    marketplace_description: str | None = None
    base_price_usdc: int | None = None


class OrgTool(BaseModel):
    id: str
    org_id: str
    name: str
    description: str
    input_schema: dict[str, Any]
    webhook_url: str
    webhook_method: str = "POST"
    has_auth: bool = False
    is_active: bool = True
    publish_as_mcp: bool = False
    marketplace_description: str | None = None
    base_price_usdc: int | None = None
    created_at: str = ""
    updated_at: str = ""

    model_config = {"extra": "allow"}


CustomTool = OrgTool


class TestWebhookRequest(BaseModel):
    """Request body for POST /tools/test-webhook (pre-publish diagnostic probe)."""

    webhook_url: str = Field(..., max_length=2048)
    webhook_method: str = Field(default="POST", pattern=r"^(GET|POST|PUT)$")
    payload: dict[str, Any] = Field(default_factory=dict)
    auth_header_name: str | None = Field(default=None, max_length=64)
    auth_header_value: str | None = Field(default=None, max_length=4096)
    timeout_seconds: int = Field(default=10, ge=1, le=30)


class TestWebhookResponse(BaseModel):
    """Diagnostic result of a test webhook invocation (always HTTP 200 on proxy success)."""

    success: bool
    status_code: int | None = None
    latency_ms: int
    response_body: dict[str, Any] | None = None
    error: str | None = None
