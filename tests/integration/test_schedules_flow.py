"""Integration tests for schedule CRUD and update behavior.

Write operations are self-cleaning: every schedule created by a test is
deleted in a ``finally`` block.

Skipped automatically when integration env vars are not set.
"""

from __future__ import annotations

import uuid

from teardrop.client import AsyncTeardropClient
from teardrop.models import CreateScheduleRequest, ScheduledRun, UpdateScheduleRequest


class TestScheduleRoundTrip:
    async def test_create_get_update_list_delete(self, async_client: AsyncTeardropClient) -> None:
        schedule: ScheduledRun | None = None
        name = f"smokeschedule_{uuid.uuid4().hex[:8]}"
        try:
            schedule = await async_client.schedules.create(
                CreateScheduleRequest(
                    name=name,
                    prompt="Integration test schedule prompt",
                    interval_seconds=3600,
                )
            )
            assert schedule.id
            assert schedule.name == name

            fetched = await async_client.schedules.get(schedule.id)
            assert fetched.id == schedule.id
            assert fetched.name == name

            updated = await async_client.schedules.update(
                schedule.id,
                UpdateScheduleRequest(
                    prompt="Updated integration test schedule prompt",
                    enabled=False,
                ),
            )
            assert updated.id == schedule.id
            assert updated.prompt == "Updated integration test schedule prompt"
            assert updated.enabled is False

            listed = await async_client.schedules.list()
            assert any(item.id == schedule.id for item in listed.items)
        finally:
            if schedule is not None:
                await async_client.schedules.delete(schedule.id)
