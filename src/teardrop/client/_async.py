"""Asynchronous Teardrop client composed from domain mixins."""

from __future__ import annotations

from teardrop.client._core import _AsyncClientBase
from teardrop.client.a2a import _A2AMixin
from teardrop.client.agent import _AgentMixin
from teardrop.client.agent_card import _AgentCardMixin
from teardrop.client.auth import _AuthMixin
from teardrop.client.billing import _BillingMixin
from teardrop.client.event_triggers import EventTriggersModule
from teardrop.client.llm import _LlmMixin
from teardrop.client.marketplace import _MarketplaceMixin
from teardrop.client.mcp import _McpMixin
from teardrop.client.memory import _MemoryMixin
from teardrop.client.schedules import SchedulesModule
from teardrop.client.tools import _ToolsMixin
from teardrop.client.usage import _UsageMixin
from teardrop.client.wallets import _WalletsMixin


class AsyncTeardropClient(
    _AgentMixin,
    _AuthMixin,
    _BillingMixin,
    _UsageMixin,
    _WalletsMixin,
    _AgentCardMixin,
    _ToolsMixin,
    _McpMixin,
    _MemoryMixin,
    _MarketplaceMixin,
    _LlmMixin,
    _A2AMixin,
    _AsyncClientBase,
):
    """Async client for the Teardrop API."""

    def __init__(
        self,
        base_url: str,
        *,
        email: str | None = None,
        secret: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        token: str | None = None,
        timeout: float = 120.0,
        discovery_timeout: float = 10.0,
    ):
        super().__init__(
            base_url,
            email=email,
            secret=secret,
            client_id=client_id,
            client_secret=client_secret,
            token=token,
            timeout=timeout,
            discovery_timeout=discovery_timeout,
        )
        self.schedules = SchedulesModule(self)
        self.event_triggers = EventTriggersModule(self)
