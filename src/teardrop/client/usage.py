"""Usage reporting client methods."""

from __future__ import annotations

import warnings
from typing import Any

from teardrop.client._core import _quote_path_segment
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

    async def get_admin_usage_org(
        self,
        org_id: str,
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> UsageSummary:
        warnings.warn(
            "get_admin_usage_org() is deprecated; use "
            "AsyncAdminTeardropClient.admin_get_usage_org() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        http = await self._get_http()
        params: dict[str, Any] = {}
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
        resp = await http.get(
            f"{self._base_url}/admin/usage/org/{_quote_path_segment(org_id)}",
            headers=await self._headers(),
            params=params or None,
        )
        self._raise_for_status(resp)
        return UsageSummary.model_validate(resp.json())

    async def get_admin_usage_user(
        self,
        user_id: str,
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> UsageSummary:
        warnings.warn(
            "get_admin_usage_user() is deprecated; use "
            "AsyncAdminTeardropClient.admin_get_usage_user() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        http = await self._get_http()
        params: dict[str, Any] = {}
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
        resp = await http.get(
            f"{self._base_url}/admin/usage/{_quote_path_segment(user_id)}",
            headers=await self._headers(),
            params=params or None,
        )
        self._raise_for_status(resp)
        return UsageSummary.model_validate(resp.json())
