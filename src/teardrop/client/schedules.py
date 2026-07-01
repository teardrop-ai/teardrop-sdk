"""Schedule sub-resource clients."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterator, Iterator

from teardrop.client._core import _parse_list_response, _parse_scheduled_runs_page
from teardrop.models import (
    CreateScheduleRequest,
    ScheduledRun,
    ScheduledRunResult,
    ScheduledRunsPage,
    UpdateScheduleRequest,
)

if TYPE_CHECKING:
    from teardrop.client._async import AsyncTeardropClient
    from teardrop.client._sync import TeardropClient


class SchedulesModule:
    def __init__(self, client: AsyncTeardropClient) -> None:
        self._c = client

    async def create(self, request: CreateScheduleRequest) -> ScheduledRun:
        http = await self._c._get_http()
        resp = await http.post(
            f"{self._c._base_url}/agent/schedules",
            json=request.model_dump(exclude_none=True),
            headers=await self._c._headers(),
        )
        self._c._raise_for_status(resp)
        return ScheduledRun.model_validate(resp.json())

    async def list(self) -> list[ScheduledRun]:
        http = await self._c._get_http()
        resp = await http.get(
            f"{self._c._base_url}/agent/schedules",
            headers=await self._c._headers(),
        )
        self._c._raise_for_status(resp)
        return _parse_list_response(resp.json(), ScheduledRun)

    async def get(self, schedule_id: str) -> ScheduledRun:
        http = await self._c._get_http()
        resp = await http.get(
            f"{self._c._base_url}/agent/schedules/{schedule_id}",
            headers=await self._c._headers(),
        )
        self._c._raise_for_status(resp)
        return ScheduledRun.model_validate(resp.json())

    async def update(self, schedule_id: str, request: UpdateScheduleRequest) -> ScheduledRun:
        http = await self._c._get_http()
        resp = await http.patch(
            f"{self._c._base_url}/agent/schedules/{schedule_id}",
            json=request.model_dump(exclude_unset=True),
            headers=await self._c._headers(),
        )
        self._c._raise_for_status(resp)
        return ScheduledRun.model_validate(resp.json())

    async def delete(self, schedule_id: str) -> None:
        http = await self._c._get_http()
        resp = await http.delete(
            f"{self._c._base_url}/agent/schedules/{schedule_id}",
            headers=await self._c._headers(),
        )
        self._c._raise_for_status(resp)

    async def runs(
        self,
        schedule_id: str,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> ScheduledRunsPage:
        http = await self._c._get_http()
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor
        resp = await http.get(
            f"{self._c._base_url}/agent/schedules/{schedule_id}/runs",
            headers=await self._c._headers(),
            params=params,
        )
        self._c._raise_for_status(resp)
        return _parse_scheduled_runs_page(resp.json())

    async def runs_iter(
        self,
        schedule_id: str,
        *,
        limit: int = 100,
        cursor: str | None = None,
    ) -> AsyncIterator[ScheduledRunResult]:
        next_cursor = cursor
        while True:
            page = await self.runs(schedule_id, limit=limit, cursor=next_cursor)
            for item in page.items:
                yield item
            if not page.next_cursor:
                break
            next_cursor = page.next_cursor


class _SyncSchedulesModule:
    def __init__(self, client: TeardropClient) -> None:
        self._c = client

    def create(self, request: CreateScheduleRequest) -> ScheduledRun:
        return self._c._run(self._c._async.schedules.create(request))

    def list(self) -> list[ScheduledRun]:
        return self._c._run(self._c._async.schedules.list())

    def get(self, schedule_id: str) -> ScheduledRun:
        return self._c._run(self._c._async.schedules.get(schedule_id))

    def update(self, schedule_id: str, request: UpdateScheduleRequest) -> ScheduledRun:
        return self._c._run(self._c._async.schedules.update(schedule_id, request))

    def delete(self, schedule_id: str) -> None:
        return self._c._run(self._c._async.schedules.delete(schedule_id))

    def runs(
        self,
        schedule_id: str,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> ScheduledRunsPage:
        return self._c._run(self._c._async.schedules.runs(schedule_id, limit=limit, cursor=cursor))

    def runs_iter(
        self,
        schedule_id: str,
        *,
        limit: int = 100,
        cursor: str | None = None,
    ) -> Iterator[ScheduledRunResult]:
        next_cursor = cursor
        while True:
            page = self.runs(schedule_id, limit=limit, cursor=next_cursor)
            for item in page.items:
                yield item
            if not page.next_cursor:
                break
            next_cursor = page.next_cursor
