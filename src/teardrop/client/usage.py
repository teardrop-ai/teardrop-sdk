"""Usage reporting client methods."""

from __future__ import annotations

from typing import Any

from teardrop.models import UsageSummary


class _UsageMixin:
    async def get_usage(
        self,
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> UsageSummary:
        http = await self._get_http()
        params: dict[str, Any] = {}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        resp = await http.get(
            f"{self._base_url}/usage/me",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        return UsageSummary.model_validate(resp.json())
