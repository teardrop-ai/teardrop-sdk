"""Teardrop SDK — Python client for the Teardrop AI agent API."""

from teardrop.client import AsyncTeardropClient, TeardropClient
from teardrop.exceptions import (
    APIError,
    AuthenticationError,
    ForbiddenError,
    PaymentRequiredError,
    RateLimitError,
    TeardropError,
)
from teardrop.models import (
    AgentCard,
    AgentRunRequest,
    BillingBalance,
    CreditHistoryEntry,
    Invoice,
    PricingInfo,
    SSEEvent,
    TokenResponse,
    UsageSummary,
    Wallet,
)
from teardrop.streaming import (
    EVENT_BILLING_SETTLEMENT,
    EVENT_DONE,
    EVENT_ERROR,
    EVENT_RUN_FINISHED,
    EVENT_RUN_STARTED,
    EVENT_STATE_SNAPSHOT,
    EVENT_SURFACE_UPDATE,
    EVENT_TEXT_MSG_CONTENT,
    EVENT_TEXT_MSG_END,
    EVENT_TEXT_MSG_START,
    EVENT_TOOL_CALL_END,
    EVENT_TOOL_CALL_START,
    EVENT_USAGE_SUMMARY,
    async_collect_text,
    collect_text,
    iter_sse_events,
)

__all__ = [
    # Clients
    "AsyncTeardropClient",
    "TeardropClient",
    # Models
    "AgentCard",
    "AgentRunRequest",
    "BillingBalance",
    "CreditHistoryEntry",
    "Invoice",
    "PricingInfo",
    "SSEEvent",
    "TokenResponse",
    "UsageSummary",
    "Wallet",
    # Exceptions
    "TeardropError",
    "AuthenticationError",
    "ForbiddenError",
    "PaymentRequiredError",
    "RateLimitError",
    "APIError",
    # Streaming
    "async_collect_text",
    "collect_text",
    "iter_sse_events",
    "EVENT_BILLING_SETTLEMENT",
    "EVENT_DONE",
    "EVENT_ERROR",
    "EVENT_RUN_FINISHED",
    "EVENT_RUN_STARTED",
    "EVENT_STATE_SNAPSHOT",
    "EVENT_SURFACE_UPDATE",
    "EVENT_TEXT_MSG_CONTENT",
    "EVENT_TEXT_MSG_END",
    "EVENT_TEXT_MSG_START",
    "EVENT_TOOL_CALL_END",
    "EVENT_TOOL_CALL_START",
    "EVENT_USAGE_SUMMARY",
]
