"""Memory-management client methods."""

from __future__ import annotations

from typing import Any

from teardrop.models import MemoryEntry, StoreMemoryRequest


class _MemoryMixin:
    async def list_memories(self, *, limit: int = 50) -> list[MemoryEntry]:
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        resp = await http.get(
            f"{self._base_url}/memories",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        data = resp.json()
        items = data["items"] if isinstance(data, dict) and "items" in data else data
        return [MemoryEntry.model_validate(m) for m in items]

    async def create_memory(self, request: StoreMemoryRequest) -> MemoryEntry:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/memories",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return MemoryEntry.model_validate(resp.json())

    async def delete_memory(self, memory_id: str) -> None:
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/memories/{memory_id}", headers=await self._headers()
        )
        self._raise_for_status(resp)
