"""Marketplace and author-payout models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MarketplaceTool(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    cost_usdc: int = 0
    author: str = ""
    author_slug: str = ""
    tool_type: str = ""


class AuthorConfig(BaseModel):
    org_id: str
    settlement_wallet: str
    created_at: str = ""
    updated_at: str = ""


class EarningsEntry(BaseModel):
    id: str
    tool_name: str
    total_cost_usdc: int = 0
    caller_org_id: str = ""
    author_share_usdc: int = 0
    platform_share_usdc: int = 0
    status: str = ""
    created_at: str = ""


class WithdrawRequest(BaseModel):
    amount_usdc: int


class MarketplaceSubscription(BaseModel):
    id: str
    org_id: str
    qualified_tool_name: str
    is_active: bool = True
    subscribed_at: str = ""


class MarketplaceImportPreviewRequest(BaseModel):
    """Request body for POST /marketplace/import/preview."""

    server_id: str = Field(..., min_length=1, max_length=128)
    tool_names: list[str] | None = None


class MarketplaceImportPublishToolRequest(BaseModel):
    """A single tool entry within POST /marketplace/import/publish."""

    remote_tool_name: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(..., min_length=1, max_length=500)
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    marketplace_description: str | None = Field(default=None, max_length=1000)
    base_price_usdc: int = Field(default=0, ge=0, le=100_000_000)
    category: str = ""


class MarketplaceImportPublishRequest(BaseModel):
    """Request body for POST /marketplace/import/publish."""

    server_id: str = Field(..., min_length=1, max_length=128)
    tools: list[MarketplaceImportPublishToolRequest] = Field(..., min_length=1, max_length=50)


class RunFeedbackRequest(BaseModel):
    """Request body for POST /marketplace/tools/{org_slug}/{tool_name}/feedback."""

    run_id: str = Field(..., min_length=1, max_length=128)
    rating: int = Field(..., ge=-1, le=1, description="-1 (bad), 0 (neutral), or 1 (good).")
    comment: str = Field(default="", max_length=1000)


class PreviewToolSchemaStatus(BaseModel):
    """Status indicating how input and output schemas were resolved."""

    input: str
    output: str


class PreviewToolDroppedSchemaFeatures(BaseModel):
    """Features trimmed or resolved during JSON Schema normalization."""

    input: list[str] = Field(default_factory=list)
    output: list[str] = Field(default_factory=list)


class PreviewTool(BaseModel):
    """A tool available on the MCP server mapped for import preview."""

    remote_tool_name: str
    proposed_name: str
    description: str
    marketplace_description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    schema_status: PreviewToolSchemaStatus
    dropped_schema_features: PreviewToolDroppedSchemaFeatures
    name_adjusted: bool
    name_collision_resolved: bool
    quota_exceeded: bool
    publishable: bool
    suggested_base_price_usdc: int
    category: str = ""
    warnings: list[str] = Field(default_factory=list)


class ParserError(BaseModel):
    """An error indicating parsing/validation failure for a tool preview."""

    remote_tool_name: str
    status_code: int
    error: str


class MarketplaceImportPreviewResponse(BaseModel):
    """Response payload for GET/POST /marketplace/import/preview."""

    server_id: str
    slots_remaining: int
    can_publish: bool
    blockers: list[str] = Field(default_factory=list)
    tools: list[PreviewTool] = Field(default_factory=list)
    errors: list[ParserError] = Field(default_factory=list)


class CreatedToolDetail(BaseModel):
    """Details of a programmatically created custom tool."""

    id: str
    name: str
    org_id: str
    publish_as_mcp: bool
    mcp_server_id: str
    mcp_tool_name: str
    base_price_usdc: int


class CreatedTool(BaseModel):
    """A published tool mapped to its remote MCP name."""

    remote_tool_name: str
    tool: CreatedToolDetail


class PublishError(BaseModel):
    """Failure details for a specific tool import action."""

    remote_tool_name: str
    name: str = ""
    status_code: int
    error: str


class MarketplaceImportPublishResponse(BaseModel):
    """Response payload for POST /marketplace/import/publish."""

    server_id: str
    created: list[CreatedTool] = Field(default_factory=list)
    errors: list[PublishError] = Field(default_factory=list)


class MarketplaceToolFeedbackResponse(BaseModel):
    """Persisted quality feedback for a marketplace tool call."""

    id: str
    run_id: str
    qualified_tool_name: str
    rating: int
    created_at: str
