"""Memory-management client methods."""

from __future__ import annotations

from typing import Any

from teardrop.client._core import _quote_path_segment
from teardrop.models import (
    MemoryCreatedResponse,
    MemoryDeletedResponse,
    MemoryListResponse,
    StoreMemoryRequest,
)


class _MemoryMixin:
    async def list_memories(self, *, limit: int = 50) -> MemoryListResponse:
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        resp = await http.get(
            f"{self._base_url}/memories",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        return MemoryListResponse.model_validate(resp.json())

    async def create_memory(self, request: StoreMemoryRequest) -> MemoryCreatedResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/memories",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return MemoryCreatedResponse.model_validate(resp.json())

    async def delete_memory(self, memory_id: str) -> MemoryDeletedResponse:
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/memories/{_quote_path_segment(memory_id)}",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return MemoryDeletedResponse.model_validate(resp.json())
