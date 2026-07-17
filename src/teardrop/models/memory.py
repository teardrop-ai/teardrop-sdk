"""Memory entry models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StoreMemoryRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)


class MemoryEntry(BaseModel):
    id: str
    content: str
    created_at: str = ""


class MemoryListItem(MemoryEntry):
    """Alias matching the OpenAPI schema item name."""


class MemoryListResponse(BaseModel):
    """Response from GET /memories."""

    items: list[MemoryEntry] = Field(default_factory=list)
    next_cursor: str | None = None


class MemoryCreatedResponse(MemoryEntry):
    """Response from POST /memories — alias matching OpenAPI schema."""


class MemoryDeletedResponse(BaseModel):
    """Response from DELETE /memories/{memory_id}."""

    id: str
    deleted_at: str = ""

    model_config = {"extra": "allow"}


class AdminMemoryItem(MemoryEntry):
    """Item inside AdminMemoryListResponse."""

    org_id: str = ""
    user_id: str = ""


class AdminMemoryListResponse(BaseModel):
    """Response from GET /admin/memories/org/{org_id}."""

    items: list[AdminMemoryItem] = Field(default_factory=list)
    next_cursor: str | None = None


class AdminMemoryPurgeResponse(BaseModel):
    """Response from DELETE /admin/memories/org/{org_id}."""

    org_id: str
    purged_count: int
    purged_at: str = ""

    model_config = {"extra": "allow"}
