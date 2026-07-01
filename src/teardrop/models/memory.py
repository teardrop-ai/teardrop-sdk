"""Memory entry models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StoreMemoryRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)


class MemoryEntry(BaseModel):
    id: str
    content: str
    created_at: str = ""
