"""Memory entry models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class StoreMemoryRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)


class MemoryEntry(BaseModel):
    id: str
    content: str
    created_at: str = ""
    source_run_id: str | None = None


class MemoryListItem(MemoryEntry):
    """Alias matching the OpenAPI schema item name."""


class MemoryListResponse(BaseModel):
    """Response from GET /memories."""

    items: list[MemoryEntry] = Field(default_factory=list)
    next_cursor: str | None = None
    total: int = 0


class MemoryCreatedResponse(MemoryEntry):
    """Response from POST /memories — alias matching OpenAPI schema."""


class MemoryDeletedResponse(BaseModel):
    """Response from DELETE /memories/{memory_id}."""

    status: Literal["deleted"]


class AdminMemoryItem(MemoryEntry):
    """Item inside AdminMemoryListResponse."""

    created_at: str
    user_id: str
    org_id: str = ""


class AdminMemoryListResponse(BaseModel):
    """Response from GET /admin/memories/org/{org_id}."""

    items: list[AdminMemoryItem]
    total: int


class AdminMemoryPurgeResponse(BaseModel):
    """Response from DELETE /admin/memories/org/{org_id}."""

    status: Literal["purged"]
    deleted: int
