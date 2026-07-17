"""Teardrop API client - async-first with sync wrapper."""

import httpx

from teardrop.client._admin_async import AsyncAdminTeardropClient
from teardrop.client._admin_sync import AdminTeardropClient
from teardrop.client._async import AsyncTeardropClient
from teardrop.client._core import (
    _AGENT_CARD_MAX_BYTES,
    _AGENT_CARD_TTL,
    _LLM_CONFIG_TTL,
    _MODEL_BENCHMARKS_TTL,
    _UNSET,
    _HttpProxy,
    _parse_list_response,
    _parse_scheduled_runs_page,
)
from teardrop.client._sync import TeardropClient
from teardrop.client.event_triggers import EventTriggersModule, _SyncEventTriggersModule
from teardrop.client.schedules import SchedulesModule, _SyncSchedulesModule

AsyncTeardropClient.__module__ = __name__
AsyncAdminTeardropClient.__module__ = __name__
AdminTeardropClient.__module__ = __name__
TeardropClient.__module__ = __name__
SchedulesModule.__module__ = __name__
EventTriggersModule.__module__ = __name__
_SyncSchedulesModule.__module__ = __name__
_SyncEventTriggersModule.__module__ = __name__
_HttpProxy.__module__ = __name__

__all__ = [
    "AsyncTeardropClient",
    "AsyncAdminTeardropClient",
    "AdminTeardropClient",
    "TeardropClient",
    "SchedulesModule",
    "EventTriggersModule",
    "httpx",
    "_SyncSchedulesModule",
    "_SyncEventTriggersModule",
    "_HttpProxy",
    "_parse_list_response",
    "_parse_scheduled_runs_page",
    "_UNSET",
    "_AGENT_CARD_TTL",
    "_AGENT_CARD_MAX_BYTES",
    "_LLM_CONFIG_TTL",
    "_MODEL_BENCHMARKS_TTL",
]
