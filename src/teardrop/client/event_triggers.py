"""Event-trigger sub-resource clients."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterator, Iterator

from teardrop.client._core import _parse_scheduled_runs_page
from teardrop.models import (
    CreateEventTriggerRequest,
    EventTrigger,
    EventTriggerCreatedResponse,
    EventTriggerListResponse,
    RotateSecretResponse,
    ScheduleDeletedResponse,
    ScheduledRunResult,
    ScheduledRunsPage,
    UpdateEventTriggerRequest,
)

if TYPE_CHECKING:
    from teardrop.client._async import AsyncTeardropClient
    from teardrop.client._sync import TeardropClient


class EventTriggersModule:
    def __init__(self, client: AsyncTeardropClient) -> None:
        self._c = client

    async def create(self, request: CreateEventTriggerRequest) -> EventTriggerCreatedResponse:
        http = await self._c._get_http()
        resp = await http.post(
            f"{self._c._base_url}/agent/event-triggers",
            json=request.model_dump(exclude_none=True),
            headers=await self._c._headers(),
        )
        self._c._raise_for_status(resp)
        return EventTriggerCreatedResponse.model_validate(resp.json())

    async def list(self) -> EventTriggerListResponse:
        http = await self._c._get_http()
        resp = await http.get(
            f"{self._c._base_url}/agent/event-triggers",
            headers=await self._c._headers(),
        )
        self._c._raise_for_status(resp)
        return EventTriggerListResponse.model_validate(resp.json())

    async def get(self, trigger_id: str) -> EventTrigger:
        http = await self._c._get_http()
        resp = await http.get(
            f"{self._c._base_url}/agent/event-triggers/{trigger_id}",
            headers=await self._c._headers(),
        )
        self._c._raise_for_status(resp)
        return EventTrigger.model_validate(resp.json())

    async def update(self, trigger_id: str, request: UpdateEventTriggerRequest) -> EventTrigger:
        http = await self._c._get_http()
        resp = await http.patch(
            f"{self._c._base_url}/agent/event-triggers/{trigger_id}",
            json=request.model_dump(exclude_unset=True),
            headers=await self._c._headers(),
        )
        self._c._raise_for_status(resp)
        return EventTrigger.model_validate(resp.json())

    async def delete(self, trigger_id: str) -> ScheduleDeletedResponse:
        http = await self._c._get_http()
        resp = await http.delete(
            f"{self._c._base_url}/agent/event-triggers/{trigger_id}",
            headers=await self._c._headers(),
        )
        self._c._raise_for_status(resp)
        return ScheduleDeletedResponse.model_validate(resp.json())

    async def rotate_secret(self, trigger_id: str) -> RotateSecretResponse:
        http = await self._c._get_http()
        resp = await http.post(
            f"{self._c._base_url}/agent/event-triggers/{trigger_id}/rotate-secret",
            headers=await self._c._headers(),
        )
        self._c._raise_for_status(resp)
        return RotateSecretResponse.model_validate(resp.json())

    async def runs(
        self,
        trigger_id: str,
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
            f"{self._c._base_url}/agent/event-triggers/{trigger_id}/runs",
            headers=await self._c._headers(),
            params=params,
        )
        self._c._raise_for_status(resp)
        return _parse_scheduled_runs_page(resp.json())

    async def runs_iter(
        self,
        trigger_id: str,
        *,
        limit: int = 100,
        cursor: str | None = None,
    ) -> AsyncIterator[ScheduledRunResult]:
        next_cursor = cursor
        while True:
            page = await self.runs(trigger_id, limit=limit, cursor=next_cursor)
            for item in page.items:
                yield item
            if not page.next_cursor:
                break
            next_cursor = page.next_cursor


class _SyncEventTriggersModule:
    def __init__(self, client: TeardropClient) -> None:
        self._c = client

    def create(self, request: CreateEventTriggerRequest) -> EventTriggerCreatedResponse:
        return self._c._run(self._c._async.event_triggers.create(request))

    def list(self) -> EventTriggerListResponse:
        return self._c._run(self._c._async.event_triggers.list())

    def get(self, trigger_id: str) -> EventTrigger:
        return self._c._run(self._c._async.event_triggers.get(trigger_id))

    def update(self, trigger_id: str, request: UpdateEventTriggerRequest) -> EventTrigger:
        return self._c._run(self._c._async.event_triggers.update(trigger_id, request))

    def delete(self, trigger_id: str) -> ScheduleDeletedResponse:
        return self._c._run(self._c._async.event_triggers.delete(trigger_id))

    def rotate_secret(self, trigger_id: str) -> RotateSecretResponse:
        return self._c._run(self._c._async.event_triggers.rotate_secret(trigger_id))

    def runs(
        self,
        trigger_id: str,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> ScheduledRunsPage:
        return self._c._run(
            self._c._async.event_triggers.runs(trigger_id, limit=limit, cursor=cursor)
        )

    def runs_iter(
        self,
        trigger_id: str,
        *,
        limit: int = 100,
        cursor: str | None = None,
    ) -> Iterator[ScheduledRunResult]:
        next_cursor = cursor
        while True:
            page = self.runs(trigger_id, limit=limit, cursor=next_cursor)
            for item in page.items:
                yield item
            if not page.next_cursor:
                break
            next_cursor = page.next_cursor
