"""Teardrop API client — async-first with sync wrapper."""

from __future__ import annotations

import uuid
from typing import Any, AsyncIterator, Iterator

import httpx

from teardrop.auth import TokenManager
from teardrop.exceptions import (
    APIError,
    AuthenticationError,
    PaymentRequiredError,
    RateLimitError,
)
from teardrop.models import (
    AgentCard,
    BillingBalance,
    CreditHistoryEntry,
    Invoice,
    PricingInfo,
    SSEEvent,
    UsageSummary,
    Wallet,
)
from teardrop.streaming import iter_sse_events


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
    ):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._token_manager = TokenManager(
            base_url,
            email=email,
            secret=secret,
            client_id=client_id,
            client_secret=client_secret,
            token=token,
        )
        self._http: httpx.AsyncClient | None = None

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
        if resp.status_code == 429:
            detail = body.get("detail", "Rate limit exceeded") if isinstance(body, dict) else str(body)
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

        body = {
            "message": message,
            "thread_id": thread_id or str(uuid.uuid4()),
        }
        if context:
            body["context"] = context

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
        return resp.json()

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
        return resp.json()

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

    async def get_agent_card(self) -> AgentCard:
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/.well-known/agent-card.json")
        self._raise_for_status(resp)
        return AgentCard.model_validate(resp.json())

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

    Uses ``anyio.from_thread.run`` so it works inside existing event loops
    (Jupyter, Django, etc.).
    """

    def __init__(self, *args: Any, **kwargs: Any):
        self._async = AsyncTeardropClient(*args, **kwargs)

    def _run(self, coro: Any) -> Any:
        import anyio.from_thread

        return anyio.from_thread.run(coro)

    def run_sync(self, message: str, **kwargs: Any) -> list[SSEEvent]:
        """Run agent and collect all events (blocking)."""
        import anyio.from_thread

        async def _collect() -> list[SSEEvent]:
            events = []
            async for event in self._async.run(message, **kwargs):
                events.append(event)
            return events

        return anyio.from_thread.run(_collect)

    def get_balance(self) -> BillingBalance:
        return self._run(self._async.get_balance())

    def get_pricing(self) -> PricingInfo:
        return self._run(self._async.get_pricing())

    def get_usage(self, **kwargs: Any) -> UsageSummary:
        return self._run(self._async.get_usage(**kwargs))

    def get_wallets(self) -> list[Wallet]:
        return self._run(self._async.get_wallets())

    def get_agent_card(self) -> AgentCard:
        return self._run(self._async.get_agent_card())

    def get_me(self) -> dict[str, Any]:
        return self._run(self._async.get_me())

    def close(self) -> None:
        self._run(self._async.close())

    def __enter__(self) -> TeardropClient:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
