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
    ConflictError,
    ForbiddenError,
    GatewayError,
    NotFoundError,
    PaymentRequiredError,
    RateLimitError,
    ValidationError,
)
from teardrop.models import (
    AgentCard,
    AgentRunRequest,
    AuthorConfig,
    BillingBalance,
    BillingHistoryEntry,
    BillingPricingResponse,
    CreateMcpServerRequest,
    CreateOrgToolRequest,
    CreditHistoryEntry,
    DiscoverMcpToolsResponse,
    EarningsEntry,
    Invoice,
    JwtPayloadBase,
    LinkWalletRequest,
    MarketplaceTool,
    MemoryEntry,
    MemoryListResponse,
    OrgMcpServer,
    OrgTool,
    SSEEvent,
    StoreMemoryRequest,
    StripeTopupRequest,
    StripeTopupResponse,
    StripeTopupStatusResponse,
    UpdateMcpServerRequest,
    UpdateOrgToolRequest,
    UsdcTopupRequest,
    UsdcTopupRequirements,
    UsageSummary,
    Wallet,
    WithdrawRequest,
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
        if resp.status_code == 404:
            detail = body.get("detail", "Not found") if isinstance(body, dict) else str(body)
            raise NotFoundError(detail)
        if resp.status_code == 409:
            detail = body.get("detail", "Conflict") if isinstance(body, dict) else str(body)
            raise ConflictError(detail)
        if resp.status_code == 422:
            detail = body.get("detail", "Validation error") if isinstance(body, dict) else str(body)
            raise ValidationError(detail)
        if resp.status_code == 429:
            detail = (
                body.get("detail", "Rate limit exceeded") if isinstance(body, dict) else str(body)
            )
            retry = int(resp.headers.get("Retry-After", "60"))
            raise RateLimitError(detail, retry_after=retry)
        if resp.status_code in (502, 504):
            detail = body.get("detail", "Bad gateway") if isinstance(body, dict) else str(body)
            raise GatewayError(detail)
        raise APIError(resp.status_code, body)

    # ─── Core: Agent ──────────────────────────────────────────────────────

    async def run(
        self,
        prompt: str,
        *,
        thread_id: str | None = None,
        model: str | None = None,
        x402_payment_header: str | None = None,
        payment_signature: str | None = None,
    ) -> AsyncIterator[SSEEvent]:
        """Stream an agent run, yielding parsed SSE events.

        Args:
            prompt: User prompt (max 4096 chars).
            thread_id: Optional conversation thread ID (auto-generated if omitted).
            model: Optional LLM model override (e.g. ``"claude-opus-4-5"``).
            x402_payment_header: x402 payment header value from a prior 402 response.
            payment_signature: EIP-3009 signature for x402 payment.
        """
        http = await self._get_http()
        headers = await self._headers()
        headers["Accept"] = "text/event-stream"

        req = AgentRunRequest(
            prompt=prompt,
            thread_id=thread_id or str(uuid.uuid4()),
            model=model,
            x402_payment_header=x402_payment_header,
            payment_signature=payment_signature,
        )
        body = req.model_dump(by_alias=True, exclude_none=True)

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

    async def get_siwe_nonce(self) -> dict[str, str]:
        """GET /auth/siwe/nonce — fetch a single-use nonce for SIWE sign-in.

        The returned nonce must be embedded in the EIP-4361 message before
        signing.  Fetch one nonce per login or wallet-link attempt.
        """
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/auth/siwe/nonce")
        self._raise_for_status(resp)
        return resp.json()

    async def authenticate_siwe(self, message: str, signature: str, nonce: str) -> str:
        """POST /token (SIWE mode) — authenticate with a pre-signed SIWE message.

        Returns the JWT and stores it for subsequent requests.
        """
        http = await self._get_http()
        return await self._token_manager.authenticate_siwe(http, message, signature, nonce)

    async def get_me(self) -> JwtPayloadBase:
        """GET /auth/me — return authenticated identity claims."""
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/auth/me", headers=await self._headers())
        self._raise_for_status(resp)
        return JwtPayloadBase.model_validate(resp.json())

    # ─── Billing ──────────────────────────────────────────────────────────

    async def get_balance(self) -> BillingBalance:
        """GET /billing/balance — org credit balance."""
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/billing/balance", headers=await self._headers())
        self._raise_for_status(resp)
        return BillingBalance.model_validate(resp.json())

    async def get_pricing(self) -> BillingPricingResponse:
        """GET /billing/pricing — tool pricing table (no auth required)."""
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/billing/pricing")
        self._raise_for_status(resp)
        return BillingPricingResponse.model_validate(resp.json())

    async def get_billing_history(
        self, *, limit: int = 20, cursor: str | None = None
    ) -> dict[str, Any]:
        """GET /billing/history — cursor-paginated run billing history."""
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        resp = await http.get(
            f"{self._base_url}/billing/history",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        data = resp.json()
        data["items"] = [BillingHistoryEntry.model_validate(i) for i in data.get("items", [])]
        return data

    async def get_invoices(
        self, *, limit: int = 20, cursor: str | None = None
    ) -> dict[str, Any]:
        """GET /billing/invoices — cursor-paginated invoice list."""
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

    async def get_invoice(self, run_id: str) -> Invoice:
        """GET /billing/invoice/{run_id} — single run invoice."""
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/billing/invoice/{run_id}",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return Invoice.model_validate(resp.json())

    async def get_credit_history(
        self, *, limit: int = 20, cursor: str | None = None
    ) -> dict[str, Any]:
        """GET /billing/credit-history — cursor-paginated credit topup history."""
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

    async def topup_stripe(self, request: StripeTopupRequest) -> StripeTopupResponse:
        """POST /billing/topup/stripe — start a Stripe checkout session."""
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/billing/topup/stripe",
            json=request.model_dump(),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return StripeTopupResponse.model_validate(resp.json())

    async def get_stripe_topup_status(self, session_id: str) -> StripeTopupStatusResponse:
        """GET /billing/topup/stripe/status — check Stripe checkout session status."""
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/billing/topup/stripe/status",
            headers=await self._headers(),
            params={"session_id": session_id},
        )
        self._raise_for_status(resp)
        return StripeTopupStatusResponse.model_validate(resp.json())

    async def get_usdc_topup_requirements(self) -> UsdcTopupRequirements:
        """GET /billing/topup/usdc/requirements — USDC topup contract parameters."""
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/billing/topup/usdc/requirements",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return UsdcTopupRequirements.model_validate(resp.json())

    async def topup_usdc(self, request: UsdcTopupRequest) -> dict[str, Any]:
        """POST /billing/topup/usdc — submit an on-chain USDC topup.

        Returns ``{"credited_usdc": <atomic USDC amount>}`` on success.
        """
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/billing/topup/usdc",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return resp.json()

    # ─── Usage ────────────────────────────────────────────────────────────

    async def get_usage(
        self,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> UsageSummary:
        """GET /usage/me — aggregated usage statistics for the current user.

        Args:
            from_date: ISO 8601 start of period (inclusive).
            to_date: ISO 8601 end of period (inclusive).
        """
        http = await self._get_http()
        params: dict[str, Any] = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        resp = await http.get(
            f"{self._base_url}/usage/me",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        return UsageSummary.model_validate(resp.json())

    # ─── Wallets ──────────────────────────────────────────────────────────

    async def link_wallet(self, request: LinkWalletRequest) -> Wallet:
        """POST /wallets/link — link a wallet via SIWE proof."""
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/wallets/link",
            json=request.model_dump(),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return Wallet.model_validate(resp.json())

    async def get_wallets(self) -> list[Wallet]:
        """GET /wallets/me — list all wallets linked to the current user."""
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/wallets/me", headers=await self._headers())
        self._raise_for_status(resp)
        return [Wallet.model_validate(w) for w in resp.json()]

    async def delete_wallet(self, wallet_id: str) -> None:
        """DELETE /wallets/{wallet_id} — unlink a wallet."""
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/wallets/{wallet_id}", headers=await self._headers()
        )
        self._raise_for_status(resp)

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

    # ─── Org Webhook Tools ────────────────────────────────────────────────

    async def create_tool(self, request: CreateOrgToolRequest) -> OrgTool:
        """POST /tools — register a new webhook-backed tool for the org."""
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/tools",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return OrgTool.model_validate(resp.json())

    async def list_tools(self) -> list[OrgTool]:
        """GET /tools — list all active tools for the org."""
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/tools", headers=await self._headers())
        self._raise_for_status(resp)
        return [OrgTool.model_validate(t) for t in resp.json()]

    async def get_tool(self, tool_id: str) -> OrgTool:
        """GET /tools/{tool_id} — fetch a single tool by ID."""
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/tools/{tool_id}", headers=await self._headers()
        )
        self._raise_for_status(resp)
        return OrgTool.model_validate(resp.json())

    async def update_tool(self, tool_id: str, request: UpdateOrgToolRequest) -> OrgTool:
        """PATCH /tools/{tool_id} — update one or more fields on a tool.

        Only explicitly-set fields on *request* are sent to the API.
        """
        http = await self._get_http()
        resp = await http.patch(
            f"{self._base_url}/tools/{tool_id}",
            json=request.model_dump(exclude_unset=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return OrgTool.model_validate(resp.json())

    async def delete_tool(self, tool_id: str) -> None:
        """DELETE /tools/{tool_id} — soft-delete a tool (sets is_active=False)."""
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/tools/{tool_id}", headers=await self._headers()
        )
        self._raise_for_status(resp)

    # ─── MCP Servers ───────────────────────────────────────────────────────────

    async def create_mcp_server(self, request: CreateMcpServerRequest) -> OrgMcpServer:
        """POST /mcp/servers — register a new external MCP server for the org."""
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/mcp/servers",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return OrgMcpServer.model_validate(resp.json())

    async def list_mcp_servers(self) -> list[OrgMcpServer]:
        """GET /mcp/servers — list active MCP servers for the org."""
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/mcp/servers", headers=await self._headers())
        self._raise_for_status(resp)
        return [OrgMcpServer.model_validate(s) for s in resp.json()]

    async def get_mcp_server(self, server_id: str) -> OrgMcpServer:
        """GET /mcp/servers/{server_id} — fetch a single MCP server by ID."""
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/mcp/servers/{server_id}", headers=await self._headers()
        )
        self._raise_for_status(resp)
        return OrgMcpServer.model_validate(resp.json())

    async def update_mcp_server(
        self, server_id: str, request: UpdateMcpServerRequest
    ) -> OrgMcpServer:
        """PATCH /mcp/servers/{server_id} — partially update an MCP server.

        Only fields explicitly set on *request* are sent to the API.
        Pass ``auth_token=None`` to explicitly clear a stored token; omitting
        ``auth_token`` entirely leaves the existing token unchanged.
        """
        http = await self._get_http()
        resp = await http.patch(
            f"{self._base_url}/mcp/servers/{server_id}",
            json=request.model_dump(exclude_unset=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return OrgMcpServer.model_validate(resp.json())

    async def delete_mcp_server(self, server_id: str) -> None:
        """DELETE /mcp/servers/{server_id} — hard-delete an MCP server.

        Permanently removes the server record and immediately stops the agent
        from using its tools.
        """
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/mcp/servers/{server_id}", headers=await self._headers()
        )
        self._raise_for_status(resp)

    async def discover_mcp_server_tools(self, server_id: str) -> DiscoverMcpToolsResponse:
        """POST /mcp/servers/{server_id}/discover — live-probe the MCP server.

        Connects to the server right now and returns its available tool schemas.
        Bypasses the agent's TTL cache. Does NOT mutate state.
        """
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/mcp/servers/{server_id}/discover",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return DiscoverMcpToolsResponse.model_validate(resp.json())

    # ─── Memory ───────────────────────────────────────────────────────────────

    async def list_memories(
        self, *, cursor: str | None = None, limit: int = 20
    ) -> MemoryListResponse:
        """GET /memories — cursor-paginated list of org memory entries."""
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        resp = await http.get(
            f"{self._base_url}/memories",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        return MemoryListResponse.model_validate(resp.json())

    async def create_memory(self, request: StoreMemoryRequest) -> MemoryEntry:
        """POST /memories — store a memory entry."""
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/memories",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return MemoryEntry.model_validate(resp.json())

    async def delete_memory(self, memory_id: str) -> None:
        """DELETE /memories/{memory_id} — delete a memory entry."""
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/memories/{memory_id}", headers=await self._headers()
        )
        self._raise_for_status(resp)

    # ─── Marketplace ──────────────────────────────────────────────────────────

    async def get_marketplace_catalog(
        self,
        *,
        cursor: str | None = None,
        limit: int = 20,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """GET /marketplace/catalog — browse published marketplace tools (no auth required)."""
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if tags:
            params["tags"] = ",".join(tags)
        resp = await http.get(f"{self._base_url}/marketplace/catalog", params=params)
        self._raise_for_status(resp)
        data = resp.json()
        data["items"] = [MarketplaceTool.model_validate(t) for t in data.get("items", [])]
        return data

    async def set_author_config(self, payout_address: str) -> AuthorConfig:
        """POST /marketplace/author-config — create or update author payout config."""
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/marketplace/author-config",
            json={"payout_address": payout_address},
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return AuthorConfig.model_validate(resp.json())

    async def get_author_config(self) -> AuthorConfig:
        """GET /marketplace/author-config — get author payout config."""
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/marketplace/author-config", headers=await self._headers()
        )
        self._raise_for_status(resp)
        return AuthorConfig.model_validate(resp.json())

    async def get_marketplace_balance(self) -> dict[str, Any]:
        """GET /marketplace/balance — author earnings balance."""
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/marketplace/balance", headers=await self._headers()
        )
        self._raise_for_status(resp)
        return resp.json()

    async def get_earnings(
        self, *, cursor: str | None = None, limit: int = 20
    ) -> dict[str, Any]:
        """GET /marketplace/earnings — cursor-paginated earnings history."""
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        resp = await http.get(
            f"{self._base_url}/marketplace/earnings",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        data = resp.json()
        data["items"] = [EarningsEntry.model_validate(e) for e in data.get("items", [])]
        return data

    async def withdraw(self, request: WithdrawRequest) -> dict[str, Any]:
        """POST /marketplace/withdraw — request a marketplace earnings payout."""
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/marketplace/withdraw",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return resp.json()

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

    def run_sync(self, prompt: str, **kwargs: Any) -> list[SSEEvent]:
        """Run agent and collect all events (blocking)."""

        async def _collect() -> list[SSEEvent]:
            events = []
            async for event in self._async.run(prompt, **kwargs):
                events.append(event)
            return events

        self._ensure_portal()
        return self._portal.call(_collect)  # type: ignore[union-attr]

    def get_siwe_nonce(self) -> dict[str, str]:
        return self._run(self._async.get_siwe_nonce())

    def authenticate_siwe(self, message: str, signature: str, nonce: str) -> str:
        return self._run(self._async.authenticate_siwe(message, signature, nonce))

    def get_me(self) -> JwtPayloadBase:
        return self._run(self._async.get_me())

    def get_balance(self) -> BillingBalance:
        return self._run(self._async.get_balance())

    def get_pricing(self) -> BillingPricingResponse:
        return self._run(self._async.get_pricing())

    def get_billing_history(self, *, limit: int = 20, cursor: str | None = None) -> dict[str, Any]:
        return self._run(self._async.get_billing_history(limit=limit, cursor=cursor))

    def get_invoices(self, *, limit: int = 20, cursor: str | None = None) -> dict[str, Any]:
        return self._run(self._async.get_invoices(limit=limit, cursor=cursor))

    def get_invoice(self, run_id: str) -> Invoice:
        return self._run(self._async.get_invoice(run_id))

    def get_credit_history(self, *, limit: int = 20, cursor: str | None = None) -> dict[str, Any]:
        return self._run(self._async.get_credit_history(limit=limit, cursor=cursor))

    def topup_stripe(self, request: StripeTopupRequest) -> StripeTopupResponse:
        return self._run(self._async.topup_stripe(request))

    def get_stripe_topup_status(self, session_id: str) -> StripeTopupStatusResponse:
        return self._run(self._async.get_stripe_topup_status(session_id))

    def get_usdc_topup_requirements(self) -> UsdcTopupRequirements:
        return self._run(self._async.get_usdc_topup_requirements())

    def topup_usdc(self, request: UsdcTopupRequest) -> dict[str, Any]:
        return self._run(self._async.topup_usdc(request))

    def get_usage(self, **kwargs: Any) -> UsageSummary:
        return self._run(self._async.get_usage(**kwargs))

    def link_wallet(self, request: LinkWalletRequest) -> Wallet:
        return self._run(self._async.link_wallet(request))

    def get_wallets(self) -> list[Wallet]:
        return self._run(self._async.get_wallets())

    def delete_wallet(self, wallet_id: str) -> None:
        return self._run(self._async.delete_wallet(wallet_id))

    def get_agent_card(self) -> AgentCard:
        return self._run(self._async.get_agent_card())

    def create_tool(self, request: CreateOrgToolRequest) -> OrgTool:
        return self._run(self._async.create_tool(request))

    def list_tools(self) -> list[OrgTool]:
        return self._run(self._async.list_tools())

    def get_tool(self, tool_id: str) -> OrgTool:
        return self._run(self._async.get_tool(tool_id))

    def update_tool(self, tool_id: str, request: UpdateOrgToolRequest) -> OrgTool:
        return self._run(self._async.update_tool(tool_id, request))

    def delete_tool(self, tool_id: str) -> None:
        return self._run(self._async.delete_tool(tool_id))

    def create_mcp_server(self, request: CreateMcpServerRequest) -> OrgMcpServer:
        return self._run(self._async.create_mcp_server(request))

    def list_mcp_servers(self) -> list[OrgMcpServer]:
        return self._run(self._async.list_mcp_servers())

    def get_mcp_server(self, server_id: str) -> OrgMcpServer:
        return self._run(self._async.get_mcp_server(server_id))

    def update_mcp_server(self, server_id: str, request: UpdateMcpServerRequest) -> OrgMcpServer:
        return self._run(self._async.update_mcp_server(server_id, request))

    def delete_mcp_server(self, server_id: str) -> None:
        return self._run(self._async.delete_mcp_server(server_id))

    def discover_mcp_server_tools(self, server_id: str) -> DiscoverMcpToolsResponse:
        return self._run(self._async.discover_mcp_server_tools(server_id))

    def list_memories(self, *, cursor: str | None = None, limit: int = 20) -> MemoryListResponse:
        return self._run(self._async.list_memories(cursor=cursor, limit=limit))

    def create_memory(self, request: StoreMemoryRequest) -> MemoryEntry:
        return self._run(self._async.create_memory(request))

    def delete_memory(self, memory_id: str) -> None:
        return self._run(self._async.delete_memory(memory_id))

    def get_marketplace_catalog(self, **kwargs: Any) -> dict[str, Any]:
        return self._run(self._async.get_marketplace_catalog(**kwargs))

    def set_author_config(self, payout_address: str) -> AuthorConfig:
        return self._run(self._async.set_author_config(payout_address))

    def get_author_config(self) -> AuthorConfig:
        return self._run(self._async.get_author_config())

    def get_marketplace_balance(self) -> dict[str, Any]:
        return self._run(self._async.get_marketplace_balance())

    def get_earnings(self, **kwargs: Any) -> dict[str, Any]:
        return self._run(self._async.get_earnings(**kwargs))

    def withdraw(self, request: WithdrawRequest) -> dict[str, Any]:
        return self._run(self._async.withdraw(request))

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
