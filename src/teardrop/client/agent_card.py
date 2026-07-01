"""Agent card discovery and caching methods."""

from __future__ import annotations

import time
from typing import Any

import httpx

from teardrop.client._core import _AGENT_CARD_MAX_BYTES, _AGENT_CARD_TTL
from teardrop.exceptions import APIError
from teardrop.models import AgentCard


class _AgentCardMixin:
    async def get_agent_card(self, *, force_refresh: bool = False) -> AgentCard:
        if (
            not force_refresh
            and self._agent_card is not None
            and time.time() < self._agent_card_fetched_at + _AGENT_CARD_TTL
        ):
            return self._agent_card

        async with self._agent_card_lock:
            if (
                not force_refresh
                and self._agent_card is not None
                and time.time() < self._agent_card_fetched_at + _AGENT_CARD_TTL
            ):
                return self._agent_card

            http = await self._get_http()
            resp = await http.get(
                f"{self._base_url}/.well-known/agent-card.json",
                timeout=httpx.Timeout(self._discovery_timeout),
            )
            self._raise_for_status(resp)

            if len(resp.content) > _AGENT_CARD_MAX_BYTES:
                raise APIError(
                    resp.status_code,
                    (
                        "Agent card response too large "
                        f"({len(resp.content)} bytes; limit {_AGENT_CARD_MAX_BYTES})"
                    ),
                )

            ct = resp.headers.get("content-type", "")
            if "application/json" not in ct:
                raise APIError(resp.status_code, f"Unexpected Content-Type for agent card: {ct!r}")

            self._agent_card = AgentCard.model_validate(resp.json())
            self._agent_card_fetched_at = time.time()
            return self._agent_card

    @classmethod
    async def from_agent_card(cls, base_url: str, **kwargs: Any):
        client = cls(base_url, **kwargs)
        await client.get_agent_card()
        return client
