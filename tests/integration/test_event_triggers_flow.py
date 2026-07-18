"""Integration tests for event-trigger CRUD and secret rotation.

Write operations are self-cleaning: every trigger created by a test is deleted
in a ``finally`` block.

Skipped automatically when integration env vars are not set.
"""

from __future__ import annotations

import uuid

from teardrop.client import AsyncTeardropClient
from teardrop.models import (
    CreateEventTriggerRequest,
    EventTriggerCreatedResponse,
    UpdateEventTriggerRequest,
)


class TestEventTriggerRoundTrip:
    async def test_create_get_update_rotate_list_delete(
        self, async_client: AsyncTeardropClient
    ) -> None:
        trigger: EventTriggerCreatedResponse | None = None
        name = f"smoketrigger_{uuid.uuid4().hex[:8]}"
        try:
            trigger = await async_client.event_triggers.create(
                CreateEventTriggerRequest(
                    name=name,
                    prompt="Integration test event-trigger prompt",
                )
            )
            assert trigger.id
            assert trigger.name == name
            assert trigger.secret

            fetched = await async_client.event_triggers.get(trigger.id)
            assert fetched.id == trigger.id
            assert fetched.name == name

            updated = await async_client.event_triggers.update(
                trigger.id,
                UpdateEventTriggerRequest(
                    prompt="Updated integration test event-trigger prompt",
                    enabled=False,
                ),
            )
            assert updated.id == trigger.id
            assert updated.prompt == "Updated integration test event-trigger prompt"
            assert updated.enabled is False

            rotated = await async_client.event_triggers.rotate_secret(trigger.id)
            assert rotated.id == trigger.id
            assert rotated.secret
            assert rotated.secret != trigger.secret

            listed = await async_client.event_triggers.list()
            assert any(item.id == trigger.id for item in listed.items)
        finally:
            if trigger is not None:
                await async_client.event_triggers.delete(trigger.id)
