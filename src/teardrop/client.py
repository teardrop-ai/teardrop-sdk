"""Teardrop API client — async-first with sync wrapper."""

from __future__ import annotations

import time
import uuid
from typing import Any, AsyncIterator

import anyio
import httpx

from teardrop.auth import TokenManager
from teardrop.exceptions import (
    APIError,
    AuthenticationError,
    ForbiddenError,
    PaymentRequiredError,
    RateLimitError,
)
from teardrop.models import (
    AgentCard,
    AgentRunRequest,
    BillingBalance,
    CreateCustomToolRequest,
    CreditHistoryEntry,
    CustomTool,
    Invoice,
    PricingInfo,
    SSEEvent,
    UsageSummary,
    Wallet,
)
from teardrop.streaming import iter_sse_events

# ─── Module constants ─────────────────────────────────────────────────────────

# Seconds before a cached agent card is considered stale and must be re-fetched.
_AGENT_CARD_TTL: int = 300
# Upper bound on the agent-card response body (64 KB).  Blocks memory-bomb payloads.
_AGENT_CARD_MAX_BYTES: int = 65_536


class AsyncTeardropClient:
    """Async client for the Teardrop API.

    Usage::

        async with AsyncTeardropClient("https://api.teardrop.dev", email="...", secret="...") as c:
            async for event in c.run("Hello"):
                print(event)
    """

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
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._discovery_timeout = discovery_timeout
        self._token_manager = TokenManager(
            base_url,
            email=email,
            secret=secret,
            client_id=client_id,
            client_secret=client_secret,
            token=token,
        )
        self._http: httpx.AsyncClient | None = None
        # Agent-card cache
        self._agent_card: AgentCard | None = None
        self._agent_card_fetched_at: float = 0.0
        self._agent_card_lock: anyio.Lock = anyio.Lock()

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=self._timeout)
        return self._http

    async def _headers(self) -> dict[str, str]:
        http = await self._get_http()
        token = await self._token_manager.get_token(http)
        return {"Authorization": f"Bearer {token}"}

    def _raise_for_status(self, resp: httpx.Response) -> None:
        """Raise typed exceptions for non-2xx responses."""
        if resp.is_success:
            return
        body: Any = None
        try:
            body = resp.json()
        except Exception:
            body = resp.text

        if resp.status_code == 401:
            detail = body.get("detail", "Unauthorized") if isinstance(body, dict) else str(body)
            raise AuthenticationError(detail)
        if resp.status_code == 402:
            detail = body.get("error", "Payment required") if isinstance(body, dict) else str(body)
            reqs = body if isinstance(body, dict) else {}
            raise PaymentRequiredError(detail, requirements=reqs)
        if resp.status_code == 403:
            detail = body.get("detail", "Forbidden") if isinstance(body, dict) else str(body)
            raise ForbiddenError(detail)
        if resp.status_code == 429:
            detail = (
                body.get("detail", "Rate limit exceeded") if isinstance(body, dict) else str(body)
            )
            retry = int(resp.headers.get("Retry-After", "60"))
            raise RateLimitError(detail, retry_after=retry)
        raise APIError(resp.status_code, body)

    # ─── Core: Agent ──────────────────────────────────────────────────────

    async def run(
        self,
        message: str,
        *,
        thread_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> AsyncIterator[SSEEvent]:
        """Stream an agent run, yielding parsed SSE events.

        Args:
            message: User message (max 4096 chars).
            thread_id: Optional conversation thread ID (auto-generated if omitted).
            context: Optional key-value context dict.
        """
        http = await self._get_http()
        headers = await self._headers()
        headers["Accept"] = "text/event-stream"

        req = AgentRunRequest(
            message=message,
            thread_id=thread_id or str(uuid.uuid4()),
            context=context or {},
        )
        body = req.model_dump()

        async with http.stream(
            "POST",
            f"{self._base_url}/agent/run",
            json=body,
            headers=headers,
            timeout=self._timeout,
        ) as resp:
            if not resp.is_success:
                await resp.aread()
                self._raise_for_status(resp)
            async for event in iter_sse_events(resp):
                yield event

    # ─── Auth ─────────────────────────────────────────────────────────────

    async def authenticate_siwe(self, siwe_message: str, siwe_signature: str) -> str:
        """Authenticate with a pre-signed SIWE message. Returns the JWT."""
        http = await self._get_http()
        return await self._token_manager.authenticate_siwe(http, siwe_message, siwe_signature)

    async def get_me(self) -> dict[str, Any]:
        """GET /auth/me — return authenticated identity claims."""
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/auth/me", headers=await self._headers())
        self._raise_for_status(resp)
        return resp.json()

    # ─── Billing ──────────────────────────────────────────────────────────

    async def get_balance(self) -> BillingBalance:
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/billing/balance", headers=await self._headers())
        self._raise_for_status(resp)
        return BillingBalance.model_validate(resp.json())

    async def get_pricing(self) -> PricingInfo:
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/billing/pricing")
        self._raise_for_status(resp)
        return PricingInfo.model_validate(resp.json())

    async def get_invoices(
        self, *, limit: int = 20, cursor: str | None = None
    ) -> dict[str, Any]:
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        resp = await http.get(
            f"{self._base_url}/billing/invoices",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        data = resp.json()
        data["items"] = [Invoice.model_validate(i) for i in data.get("items", [])]
        return data

    async def get_credit_history(
        self, *, limit: int = 20, cursor: str | None = None
    ) -> dict[str, Any]:
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        resp = await http.get(
            f"{self._base_url}/billing/credit-history",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        data = resp.json()
        data["items"] = [CreditHistoryEntry.model_validate(i) for i in data.get("items", [])]
        return data

    async def topup_stripe(self, amount_cents: int, return_url: str) -> dict[str, Any]:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/billing/topup/stripe",
            json={"amount_cents": amount_cents, "return_url": return_url},
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return resp.json()

    # ─── Usage ────────────────────────────────────────────────────────────

    async def get_usage(self, *, days: int = 30) -> UsageSummary:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/usage/me",
            headers=await self._headers(),
            params={"days": days},
        )
        self._raise_for_status(resp)
        return UsageSummary.model_validate(resp.json())

    # ─── Wallets ──────────────────────────────────────────────────────────

    async def get_wallets(self) -> list[Wallet]:
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/wallets/me", headers=await self._headers())
        self._raise_for_status(resp)
        return [Wallet.model_validate(w) for w in resp.json()]

    # ─── Agent card ───────────────────────────────────────────────────────

    async def get_agent_card(self, *, force_refresh: bool = False) -> AgentCard:
        """Fetch and cache the agent card from ``/.well-known/agent-card.json``.

        The result is cached for ``_AGENT_CARD_TTL`` seconds (default 5 min).
        Pass ``force_refresh=True`` to bypass the cache unconditionally.

        Security hardening on every live fetch:

        - Response body is capped at 64 KB to block memory-bomb payloads.
        - ``Content-Type`` must contain ``application/json``.
        - Uses ``discovery_timeout`` (default 10 s), isolated from the 120 s
          API timeout, so a slow metadata endpoint cannot stall real requests.
        """
        # Fast path: cache is warm.
        if (
            not force_refresh
            and self._agent_card is not None
            and time.time() < self._agent_card_fetched_at + _AGENT_CARD_TTL
        ):
            return self._agent_card

        async with self._agent_card_lock:
            # Double-checked locking: re-validate inside the lock so concurrent
            # coroutines that both missed the fast path only issue one HTTP request.
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
                    f"Agent card response too large "
                    f"({len(resp.content)} bytes; limit {_AGENT_CARD_MAX_BYTES})",
                )

            ct = resp.headers.get("content-type", "")
            if "application/json" not in ct:
                raise APIError(
                    resp.status_code,
                    f"Unexpected Content-Type for agent card: {ct!r}",
                )

            self._agent_card = AgentCard.model_validate(resp.json())
            self._agent_card_fetched_at = time.time()
            return self._agent_card

    # ─── Custom Tools ─────────────────────────────────────────────────────

    async def create_tool(self, request: CreateCustomToolRequest) -> CustomTool:
        """POST /tools — register a new webhook-backed custom tool for the org."""
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/tools",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return CustomTool.model_validate(resp.json())

    async def list_tools(self) -> list[CustomTool]:
        """GET /tools — list all custom tools registered for the org."""
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/tools", headers=await self._headers())
        self._raise_for_status(resp)
        return [CustomTool.model_validate(t) for t in resp.json()]

    async def get_tool(self, tool_id: str) -> CustomTool:
        """GET /tools/{tool_id} — fetch a single custom tool by ID."""
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/tools/{tool_id}", headers=await self._headers()
        )
        self._raise_for_status(resp)
        return CustomTool.model_validate(resp.json())

    async def update_tool(self, tool_id: str, **fields: Any) -> CustomTool:
        """PATCH /tools/{tool_id} — update one or more fields on a custom tool.

        Pass only the fields you want to change, e.g.::

            await client.update_tool("abc", is_active=False, timeout_seconds=15)

        ``None`` values are passed through (to allow explicit null-outs).
        """
        http = await self._get_http()
        resp = await http.patch(
            f"{self._base_url}/tools/{tool_id}",
            json=fields,
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return CustomTool.model_validate(resp.json())

    async def delete_tool(self, tool_id: str) -> None:
        """DELETE /tools/{tool_id} — permanently remove a custom tool (204 No Content)."""
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/tools/{tool_id}", headers=await self._headers()
        )
        self._raise_for_status(resp)

    # ─── Factory ──────────────────────────────────────────────────────────

    @classmethod
    async def from_agent_card(cls, base_url: str, **kwargs: Any) -> AsyncTeardropClient:
        """Create a client and eagerly fetch the agent card for zero-config setup.

        The agent card is discovered and cached before any user code runs, so
        subsequent calls to ``get_agent_card()`` are free.  Misconfiguration
        (bad URL, unreachable host) surfaces at construction time rather than
        silently on the first run call.

        Usage::

            client = await AsyncTeardropClient.from_agent_card(
                "https://api.teardrop.dev", email="...", secret="..."
            )
        """
        client = cls(base_url, **kwargs)
        await client.get_agent_card()
        return client

    # ─── Lifecycle ────────────────────────────────────────────────────────

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    async def __aenter__(self) -> AsyncTeardropClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()


# ─── Sync wrapper ─────────────────────────────────────────────────────────────


class TeardropClient:
    """Synchronous wrapper around ``AsyncTeardropClient``.

    Maintains a persistent ``anyio`` blocking portal (background event-loop thread)
    so the underlying ``httpx.AsyncClient`` is reused across calls.

    Prefer using this as a context manager::

        with TeardropClient("https://api.teardrop.dev", email="...", secret="...") as client:
            events = client.run_sync("Hello")

    Without a context manager the portal is started lazily; call ``close()``
    explicitly to release the background thread.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        self._async = AsyncTeardropClient(*args, **kwargs)
        self._portal: Any | None = None
        self._portal_exit: Any | None = None

    def _ensure_portal(self) -> None:
        if self._portal is None:
            import anyio.from_thread

            cm = anyio.from_thread.start_blocking_portal()
            self._portal = cm.__enter__()
            self._portal_exit = cm.__exit__

    def _run(self, coro: Any) -> Any:
        self._ensure_portal()
        return self._portal.call(lambda: coro)  # type: ignore[union-attr]

    def run_sync(self, message: str, **kwargs: Any) -> list[SSEEvent]:
        """Run agent and collect all events (blocking)."""

        async def _collect() -> list[SSEEvent]:
            events = []
            async for event in self._async.run(message, **kwargs):
                events.append(event)
            return events

        self._ensure_portal()
        return self._portal.call(_collect)  # type: ignore[union-attr]

    def authenticate_siwe(self, siwe_message: str, siwe_signature: str) -> str:
        return self._run(self._async.authenticate_siwe(siwe_message, siwe_signature))

    def get_me(self) -> dict[str, Any]:
        return self._run(self._async.get_me())

    def get_balance(self) -> BillingBalance:
        return self._run(self._async.get_balance())

    def get_pricing(self) -> PricingInfo:
        return self._run(self._async.get_pricing())

    def get_invoices(self, *, limit: int = 20, cursor: str | None = None) -> dict[str, Any]:
        return self._run(self._async.get_invoices(limit=limit, cursor=cursor))

    def get_credit_history(self, *, limit: int = 20, cursor: str | None = None) -> dict[str, Any]:
        return self._run(self._async.get_credit_history(limit=limit, cursor=cursor))

    def topup_stripe(self, amount_cents: int, return_url: str) -> dict[str, Any]:
        return self._run(self._async.topup_stripe(amount_cents, return_url))

    def get_usage(self, **kwargs: Any) -> UsageSummary:
        return self._run(self._async.get_usage(**kwargs))

    def get_wallets(self) -> list[Wallet]:
        return self._run(self._async.get_wallets())

    def get_agent_card(self) -> AgentCard:
        return self._run(self._async.get_agent_card())

    def create_tool(self, request: CreateCustomToolRequest) -> CustomTool:
        return self._run(self._async.create_tool(request))

    def list_tools(self) -> list[CustomTool]:
        return self._run(self._async.list_tools())

    def get_tool(self, tool_id: str) -> CustomTool:
        return self._run(self._async.get_tool(tool_id))

    def update_tool(self, tool_id: str, **fields: Any) -> CustomTool:
        return self._run(self._async.update_tool(tool_id, **fields))

    def delete_tool(self, tool_id: str) -> None:
        return self._run(self._async.delete_tool(tool_id))

    def close(self) -> None:
        if self._portal is not None:
            self._portal.call(lambda: self._async.close())  # type: ignore[union-attr]
            self._portal_exit(None, None, None)  # type: ignore[misc]
            self._portal = None
            self._portal_exit = None

    @classmethod
    def from_agent_card(cls, base_url: str, **kwargs: Any) -> TeardropClient:
        """Create a sync client and eagerly fetch the agent card for zero-config setup.

        Mirrors ``AsyncTeardropClient.from_agent_card`` for the synchronous API.
        """
        client = cls(base_url, **kwargs)
        client.get_agent_card()
        return client

    def __enter__(self) -> TeardropClient:
        self._ensure_portal()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
