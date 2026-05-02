"""Teardrop API client — async-first with sync wrapper."""

from __future__ import annotations

import contextlib
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
    TeardropError,
    ValidationError,
)
from teardrop.models import (
    AddTrustedAgentRequest,
    AgentCard,
    AgentRunRequest,
    AgentWallet,
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
    MODELS_BY_PROVIDER,
    MarketplaceSubscription,
    MarketplaceTool,
    MeResponse,
    MemoryEntry,
    ModelBenchmarksResponse,
    OrgCredentialsEntry,
    OrgCredentialsResponse,
    OrgLlmConfig,
    OrgMcpServer,
    OrgTool,
    RegenerateCredentialsResponse,
    SSEEvent,
    SetLlmConfigRequest,
    StoreMemoryRequest,
    StripeTopupRequest,
    StripeTopupResponse,
    StripeTopupStatusResponse,
    TokenResponse,
    TrustedAgent,
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

# Sentinel object used to distinguish "not provided" from explicit ``None``.
# Used in ``set_llm_config`` so callers can pass ``api_key=None`` to *clear*
# BYOK rather than preserving the existing key.
_UNSET: object = object()

# Seconds before a cached agent card is considered stale and must be re-fetched.
_AGENT_CARD_TTL: int = 300
# Upper bound on the agent-card response body (64 KB).  Blocks memory-bomb payloads.
_AGENT_CARD_MAX_BYTES: int = 65_536
# Seconds before a cached org LLM config is considered stale.
_LLM_CONFIG_TTL: int = 300
# Seconds before a cached public model benchmarks response is considered stale.
_MODEL_BENCHMARKS_TTL: int = 600


class _HttpProxy:
    """Wraps ``httpx.AsyncClient`` to translate transport errors into ``TeardropError``.

    Returned by ``AsyncTeardropClient._get_http()`` so every HTTP call is
    automatically covered without modifying individual callsites.
    """

    __slots__ = ("_c",)

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._c = client

    @property
    def is_closed(self) -> bool:
        return self._c.is_closed

    async def aclose(self) -> None:
        await self._c.aclose()

    async def _call(self, method: str, url: str, **kw: Any) -> httpx.Response:
        try:
            return await getattr(self._c, method)(url, **kw)
        except httpx.ConnectError as exc:
            raise TeardropError(f"Connection failed: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise TeardropError(f"Request timed out: {exc}") from exc

    async def get(self, url: str, **kw: Any) -> httpx.Response:
        return await self._call("get", url, **kw)

    async def post(self, url: str, **kw: Any) -> httpx.Response:
        return await self._call("post", url, **kw)

    async def put(self, url: str, **kw: Any) -> httpx.Response:
        return await self._call("put", url, **kw)

    async def patch(self, url: str, **kw: Any) -> httpx.Response:
        return await self._call("patch", url, **kw)

    async def delete(self, url: str, **kw: Any) -> httpx.Response:
        return await self._call("delete", url, **kw)

    @contextlib.asynccontextmanager
    async def stream(
        self, method: str, url: str, **kw: Any
    ) -> AsyncIterator[httpx.Response]:
        try:
            async with self._c.stream(method, url, **kw) as resp:
                yield resp
        except httpx.ConnectError as exc:
            raise TeardropError(f"Connection failed: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise TeardropError(f"Request timed out: {exc}") from exc


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
        # LLM config cache (keyed by org_id for clarity; stores (OrgLlmConfig, timestamp))
        self._llm_config_cache: tuple[OrgLlmConfig, float] | None = None
        # Public model benchmarks cache
        self._model_benchmarks_cache: tuple[ModelBenchmarksResponse, float] | None = None

    async def _get_http(self) -> _HttpProxy:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=self._timeout)
        return _HttpProxy(self._http)

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
            payment_header = resp.headers.get("X-PAYMENT-REQUIRED")
            raise PaymentRequiredError(
                detail, requirements=reqs, payment_header=payment_header
            )
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
        message: str,
        *,
        thread_id: str | None = None,
        context: dict[str, Any] | None = None,
        payment_header: str | None = None,
        emit_ui: bool = True,
    ) -> AsyncIterator[SSEEvent]:
        """Stream an agent run, yielding parsed SSE events.

        Args:
            message: User message (max 4096 chars).
            thread_id: Optional conversation thread ID (auto-generated if omitted).
            context: Optional extra context passed to agent state metadata.
            payment_header: Pre-signed x402 payment header (for retry after 402).
            emit_ui: Controls whether UI surface events are emitted.
        """
        http = await self._get_http()
        headers = await self._headers()
        headers["Accept"] = "text/event-stream"

        if payment_header:
            headers["X-Payment"] = payment_header

        req = AgentRunRequest(
            message=message,
            thread_id=thread_id or str(uuid.uuid4()),
            context=context,
            emit_ui=emit_ui,
        )
        body = req.model_dump(exclude_none=True)

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
        """GET /auth/siwe/nonce — fetch a single-use nonce for SIWE sign-in."""
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/auth/siwe/nonce")
        self._raise_for_status(resp)
        return resp.json()

    async def authenticate_siwe(self, message: str, signature: str) -> str:
        """POST /token (SIWE mode) — authenticate with a pre-signed SIWE message.

        The nonce is embedded inside the SIWE message itself, not sent as a
        separate field.  Returns the JWT and stores it for subsequent requests.
        """
        http = await self._get_http()
        return await self._token_manager.authenticate_siwe(http, message, signature)

    async def get_me(self) -> MeResponse:
        """GET /auth/me — return authenticated identity claims plus org_name."""
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/auth/me", headers=await self._headers())
        self._raise_for_status(resp)
        return MeResponse.model_validate(resp.json())

    async def register(
        self, *, org_name: str, email: str, password: str
    ) -> TokenResponse:
        """POST /register — self-serve org + user registration."""
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/register",
            json={"org_name": org_name, "email": email, "password": password},
        )
        self._raise_for_status(resp)
        data = TokenResponse.model_validate(resp.json())
        self._token_manager._token = data.access_token
        self._token_manager._refresh_token = data.refresh_token
        self._token_manager._expires_at = self._token_manager._read_exp(data.access_token)
        return data

    async def register_invite(
        self, *, token: str, email: str, password: str
    ) -> TokenResponse:
        """POST /register/invite — accept org invite and create user."""
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/register/invite",
            json={"token": token, "email": email, "password": password},
        )
        self._raise_for_status(resp)
        data = TokenResponse.model_validate(resp.json())
        self._token_manager._token = data.access_token
        self._token_manager._refresh_token = data.refresh_token
        self._token_manager._expires_at = self._token_manager._read_exp(data.access_token)
        return data

    async def refresh(self, refresh_token: str) -> TokenResponse:
        """POST /auth/refresh — rotate refresh token for new access token."""
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        self._raise_for_status(resp)
        data = TokenResponse.model_validate(resp.json())
        self._token_manager._token = data.access_token
        self._token_manager._refresh_token = data.refresh_token
        self._token_manager._expires_at = self._token_manager._read_exp(data.access_token)
        return data

    async def logout(self, refresh_token: str) -> None:
        """POST /auth/logout — revoke a refresh token."""
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/auth/logout",
            json={"refresh_token": refresh_token},
            headers=await self._headers(),
        )
        self._raise_for_status(resp)

    async def verify_email(self, token: str) -> dict[str, Any]:
        """GET /auth/verify-email — verify email with one-time token."""
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/auth/verify-email",
            params={"token": token},
        )
        self._raise_for_status(resp)
        return resp.json()

    async def resend_verification(self, email: str) -> dict[str, Any]:
        """POST /auth/resend-verification — resend verification email."""
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/auth/resend-verification",
            json={"email": email},
        )
        self._raise_for_status(resp)
        return resp.json()

    async def invite(
        self, *, email: str | None = None, role: str = "member"
    ) -> dict[str, Any]:
        """POST /org/invite — create an org invite link."""
        http = await self._get_http()
        body: dict[str, Any] = {"role": role}
        if email:
            body["email"] = email
        resp = await http.post(
            f"{self._base_url}/org/invite",
            json=body,
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return resp.json()

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

    async def get_billing_history(self, *, limit: int = 20) -> list[BillingHistoryEntry]:
        """GET /billing/history — run billing history (flat array)."""
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        resp = await http.get(
            f"{self._base_url}/billing/history",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        return [BillingHistoryEntry.model_validate(i) for i in resp.json()]

    async def get_invoices(self, *, limit: int = 20) -> list[Invoice]:
        """GET /billing/invoices — invoice list."""
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        resp = await http.get(
            f"{self._base_url}/billing/invoices",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        return [Invoice.model_validate(i) for i in resp.json()]

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
        self, *, limit: int = 20, operation: str | None = None
    ) -> list[CreditHistoryEntry]:
        """GET /billing/credit-history — credit topup history."""
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        if operation:
            params["operation"] = operation
        resp = await http.get(
            f"{self._base_url}/billing/credit-history",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        data = resp.json()
        items = data["items"] if isinstance(data, dict) and "items" in data else data
        return [CreditHistoryEntry.model_validate(i) for i in items]

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

    async def get_usdc_topup_requirements(self, amount_usdc: int) -> UsdcTopupRequirements:
        """GET /billing/topup/usdc/requirements — USDC topup parameters."""
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/billing/topup/usdc/requirements",
            headers=await self._headers(),
            params={"amount_usdc": amount_usdc},
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
        start: str | None = None,
        end: str | None = None,
    ) -> UsageSummary:
        """GET /usage/me — aggregated usage statistics for the current user.

        Args:
            start: ISO 8601 start of period (inclusive).
            end: ISO 8601 end of period (inclusive).
        """
        http = await self._get_http()
        params: dict[str, Any] = {}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
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
        data = resp.json()
        if isinstance(data, dict):
            items = data.get("items") or data.get("tools") or []
        else:
            items = data
        return [OrgTool.model_validate(t) for t in items]

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
        data = resp.json()
        if isinstance(data, dict):
            items = data.get("items") or data.get("mcp_servers") or data.get("servers") or []
        else:
            items = data
        return [OrgMcpServer.model_validate(s) for s in items]

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

    async def list_memories(self, *, limit: int = 50) -> list[MemoryEntry]:
        """GET /memories — list org memory entries."""
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        resp = await http.get(
            f"{self._base_url}/memories",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        data = resp.json()
        items = data["items"] if isinstance(data, dict) and "items" in data else data
        return [MemoryEntry.model_validate(m) for m in items]

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
        org_slug: str | None = None,
        sort: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """GET /marketplace/catalog — browse published marketplace tools (no auth required).

        Args:
            org_slug: Filter by author org slug. Use ``"platform"`` for Teardrop built-in tools.
            sort: Sort order — ``"name"``, ``"price_asc"``, or ``"price_desc"`` (default: ``"name"``)
            limit: Results per page (1–200, default: 100).
            cursor: Opaque pagination token from a previous response's ``next_cursor``.

        Returns:
            ``{"tools": list[MarketplaceTool], "next_cursor": str | None}``
        """
        http = await self._get_http()
        params: dict[str, Any] = {}
        if org_slug is not None:
            params["org_slug"] = org_slug
        if sort is not None:
            params["sort"] = sort
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor
        resp = await http.get(f"{self._base_url}/marketplace/catalog", params=params)
        self._raise_for_status(resp)
        data = resp.json()
        data["tools"] = [MarketplaceTool.model_validate(t) for t in data.get("tools", [])]
        return data

    async def set_author_config(self, settlement_wallet: str) -> AuthorConfig:
        """POST /marketplace/author-config — create or update author payout config."""
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/marketplace/author-config",
            json={"settlement_wallet": settlement_wallet},
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
        self,
        *,
        limit: int = 20,
        tool_name: str | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """GET /marketplace/earnings — earnings history (cursor-paginated).

        Returns:
            ``{"earnings": list[EarningsEntry], "next_cursor": str | None}``
        """
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        if tool_name is not None:
            params["tool_name"] = tool_name
        if cursor is not None:
            params["cursor"] = cursor
        resp = await http.get(
            f"{self._base_url}/marketplace/earnings",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        data = resp.json()
        if isinstance(data, list):
            # Handle legacy flat-array response shape
            return {"earnings": [EarningsEntry.model_validate(e) for e in data], "next_cursor": None}
        data["earnings"] = [EarningsEntry.model_validate(e) for e in data.get("earnings", [])]
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

    async def get_withdrawals(
        self,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """GET /marketplace/withdrawals — withdrawal history (cursor-paginated).

        Returns:
            ``{"withdrawals": list[dict], "next_cursor": str | None}``
        """
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        resp = await http.get(
            f"{self._base_url}/marketplace/withdrawals",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        data = resp.json()
        if isinstance(data, list):
            # Handle legacy flat-array response shape
            return {"withdrawals": data, "next_cursor": None}
        return data

    async def subscribe(self, qualified_tool_name: str) -> MarketplaceSubscription:
        """POST /marketplace/subscriptions — subscribe to a marketplace tool."""
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/marketplace/subscriptions",
            json={"qualified_tool_name": qualified_tool_name},
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return MarketplaceSubscription.model_validate(resp.json())

    async def get_subscriptions(self) -> list[MarketplaceSubscription]:
        """GET /marketplace/subscriptions — list active subscriptions."""
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/marketplace/subscriptions",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        data = resp.json()
        items = data["subscriptions"] if isinstance(data, dict) and "subscriptions" in data else data
        return [MarketplaceSubscription.model_validate(s) for s in items]

    async def unsubscribe(self, subscription_id: str) -> None:
        """DELETE /marketplace/subscriptions/{id} — unsubscribe."""
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/marketplace/subscriptions/{subscription_id}",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)

    # ─── LLM Config ───────────────────────────────────────────────────────────

    async def get_llm_config(self) -> OrgLlmConfig:
        """GET /llm-config — fetch the org's current LLM configuration.

        Results are cached for 5 minutes; the cache is invalidated whenever
        ``set_llm_config`` or ``delete_llm_config`` succeeds.
        """
        now = time.time()
        if (
            self._llm_config_cache is not None
            and now < self._llm_config_cache[1] + _LLM_CONFIG_TTL
        ):
            return self._llm_config_cache[0]

        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/llm-config", headers=await self._headers())
        self._raise_for_status(resp)
        config = OrgLlmConfig.model_validate(resp.json())
        self._llm_config_cache = (config, now)
        return config

    async def set_llm_config(
        self,
        *,
        provider: str,
        model: str,
        routing_preference: str = "default",
        api_key: str | None = _UNSET,  # type: ignore[assignment]
        api_base: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        timeout_seconds: int = 120,
    ) -> OrgLlmConfig:
        """PUT /llm-config — create or update the org's LLM configuration.

        Args:
            provider: LLM provider — ``"anthropic"``, ``"openai"``, ``"google"``, or ``"openrouter"``.
            model: Model identifier (e.g. ``"claude-haiku-4-5-20251001"``).
            routing_preference: ``"default"``, ``"cost"``, ``"speed"``, or ``"quality"``.
            api_key: BYOK API key behaviour:
                - Omitted / not passed: existing key is preserved (field absent
                  from request body).
                - ``None``: explicitly clears BYOK and reverts to the shared
                  platform key (field sent as ``null``).
                - ``str``: sets a new BYOK key.  Sent over TLS only; never logged.
            api_base: Optional self-hosted endpoint URL (vLLM / Ollama / OpenRouter).
            max_tokens: Maximum tokens per response (1–200 000, default 4096).
            temperature: Sampling temperature (0–2, default 0.0).
            timeout_seconds: Per-request timeout in seconds (default 120).

        Returns:
            Updated :class:`OrgLlmConfig`.

        Raises:
            :exc:`~teardrop.exceptions.ValidationError`: ``provider`` or
                ``routing_preference`` is invalid, or ``temperature`` /
                ``max_tokens`` is out of range.
            :exc:`~teardrop.exceptions.APIError`: ``api_base`` fails SSRF
                validation (status 400).
        """
        # Validate locally before the network round-trip so the error message
        # includes which enum values are valid.
        req_kwargs: dict[str, Any] = dict(
            provider=provider,  # type: ignore[arg-type]
            model=model,
            api_base=api_base,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
            routing_preference=routing_preference,  # type: ignore[arg-type]
        )
        if api_key is not _UNSET:
            req_kwargs["api_key"] = api_key
        request = SetLlmConfigRequest(**req_kwargs)
        # Exclude None values (api_base etc.) but preserve explicit api_key=None
        # which signals the backend to clear BYOK and revert to the shared key.
        body = request.model_dump(exclude_none=True)
        if "api_key" in request.model_fields_set and request.api_key is None:
            body["api_key"] = None

        http = await self._get_http()
        resp = await http.put(
            f"{self._base_url}/llm-config",
            json=body,
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        config = OrgLlmConfig.model_validate(resp.json())
        # Invalidate cache with the fresh value.
        self._llm_config_cache = (config, time.time())
        return config

    async def clear_llm_api_key(
        self,
        *,
        provider: str,
        model: str,
        routing_preference: str = "default",
        api_base: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        timeout_seconds: int = 120,
    ) -> OrgLlmConfig:
        """PUT /llm-config with ``api_key=None`` — remove BYOK key, keep other config.

        Convenience wrapper for clients that strip ``None`` values before
        JSON serialisation.  Explicitly sends ``api_key: null`` so the backend
        reverts to the shared platform key.

        All other args are required and forwarded to the config update.
        """
        return await self.set_llm_config(
            provider=provider,
            model=model,
            routing_preference=routing_preference,
            api_key=None,
            api_base=api_base,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
        )

    async def delete_llm_config(self) -> dict[str, Any]:
        """DELETE /llm-config — remove the org's custom LLM config.

        Reverts to the global default configuration.  Returns
        ``{"status": "deleted"}`` on success.  If no config exists, the server
        returns 404 which the SDK re-raises as :exc:`~teardrop.exceptions.NotFoundError`.
        """
        http = await self._get_http()
        resp = await http.delete(f"{self._base_url}/llm-config", headers=await self._headers())
        self._raise_for_status(resp)
        # Invalidate cache.
        self._llm_config_cache = None
        return resp.json()

    # ─── Models / Benchmarks ──────────────────────────────────────────────────

    async def get_model_benchmarks(self) -> ModelBenchmarksResponse:
        """GET /models/benchmarks — public model catalogue with live metrics.

        No authentication required.  Results are cached for 10 minutes (the
        server also applies a 15-minute cache, so this is advisory only).
        """
        now = time.time()
        if (
            self._model_benchmarks_cache is not None
            and now < self._model_benchmarks_cache[1] + _MODEL_BENCHMARKS_TTL
        ):
            return self._model_benchmarks_cache[0]

        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/models/benchmarks")
        self._raise_for_status(resp)
        result = ModelBenchmarksResponse.model_validate(resp.json())
        self._model_benchmarks_cache = (result, now)
        return result

    async def get_org_model_benchmarks(self) -> ModelBenchmarksResponse:
        """GET /models/benchmarks/org — model benchmarks scoped to the caller's org.

        Auth required.  Results are **not** cached (always a fresh query).
        """
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/models/benchmarks/org", headers=await self._headers()
        )
        self._raise_for_status(resp)
        return ModelBenchmarksResponse.model_validate(resp.json())

    def list_supported_providers(self) -> list[str]:
        """Return the list of supported LLM providers (client-side constant).

        Returns:
            ``["anthropic", "openai", "google", "openrouter"]``
        """
        return list(MODELS_BY_PROVIDER.keys())

    def list_models_for_provider(self, provider: str) -> list[str]:
        """Return known model identifiers for *provider* (client-side constant).

        Args:
            provider: One of ``"anthropic"``, ``"openai"``, ``"google"``, ``"openrouter"``.

        Raises:
            :exc:`ValueError`: Unknown provider.
        """
        if provider not in MODELS_BY_PROVIDER:
            raise ValueError(
                f"Unknown provider {provider!r}. "
                f"Supported: {list(MODELS_BY_PROVIDER.keys())}"
            )
        return list(MODELS_BY_PROVIDER[provider])

    # ─── A2A Delegation ───────────────────────────────────────────────────────

    async def add_trusted_agent(self, request: AddTrustedAgentRequest) -> TrustedAgent:
        """POST /a2a/agents — add a trusted agent for delegation."""
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/a2a/agents",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return TrustedAgent.model_validate(resp.json())

    async def list_trusted_agents(self) -> list[TrustedAgent]:
        """GET /a2a/agents — list org's trusted agents."""
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/a2a/agents",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return [TrustedAgent.model_validate(a) for a in resp.json()]

    async def remove_trusted_agent(self, agent_id: str) -> None:
        """DELETE /a2a/agents/{agent_id} — remove a trusted agent."""
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/a2a/agents/{agent_id}",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)

    async def get_delegations(self, *, limit: int = 20) -> list[dict[str, Any]]:
        """GET /a2a/delegations — delegation event history."""
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        resp = await http.get(
            f"{self._base_url}/a2a/delegations",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        return resp.json()

    # ─── Agent Wallets ─────────────────────────────────────────────────────────

    async def provision_agent_wallet(self) -> AgentWallet:
        """POST /wallets/agent — provision a CDP agent wallet for the org."""
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/wallets/agent",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return AgentWallet.model_validate(resp.json())

    async def get_agent_wallet(
        self, *, include_balance: bool = False
    ) -> AgentWallet:
        """GET /wallets/agent — get org agent wallet."""
        http = await self._get_http()
        params: dict[str, Any] = {}
        if include_balance:
            params["include_balance"] = "true"
        resp = await http.get(
            f"{self._base_url}/wallets/agent",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        return AgentWallet.model_validate(resp.json())

    async def deactivate_agent_wallet(self) -> None:
        """DELETE /wallets/agent — deactivate agent wallet (admin only)."""
        http = await self._get_http()
        resp = await http.delete(
            f"{self._base_url}/wallets/agent",
            headers=await self._headers(),
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

    def get_siwe_nonce(self) -> dict[str, str]:
        return self._run(self._async.get_siwe_nonce())

    def authenticate_siwe(self, message: str, signature: str) -> str:
        return self._run(self._async.authenticate_siwe(message, signature))

    def get_me(self) -> JwtPayloadBase:
        return self._run(self._async.get_me())

    def register(self, **kwargs: Any) -> TokenResponse:
        return self._run(self._async.register(**kwargs))

    def register_invite(self, **kwargs: Any) -> TokenResponse:
        return self._run(self._async.register_invite(**kwargs))

    def refresh(self, refresh_token: str) -> TokenResponse:
        return self._run(self._async.refresh(refresh_token))

    def logout(self, refresh_token: str) -> None:
        return self._run(self._async.logout(refresh_token))

    def verify_email(self, token: str) -> dict[str, Any]:
        return self._run(self._async.verify_email(token))

    def resend_verification(self, email: str) -> dict[str, Any]:
        return self._run(self._async.resend_verification(email))

    def invite(self, **kwargs: Any) -> dict[str, Any]:
        return self._run(self._async.invite(**kwargs))

    def get_balance(self) -> BillingBalance:
        return self._run(self._async.get_balance())

    def get_pricing(self) -> BillingPricingResponse:
        return self._run(self._async.get_pricing())

    def get_billing_history(self, *, limit: int = 20) -> list[BillingHistoryEntry]:
        return self._run(self._async.get_billing_history(limit=limit))

    def get_invoices(self, *, limit: int = 20) -> list[Invoice]:
        return self._run(self._async.get_invoices(limit=limit))

    def get_invoice(self, run_id: str) -> Invoice:
        return self._run(self._async.get_invoice(run_id))

    def get_credit_history(
        self, *, limit: int = 20, operation: str | None = None
    ) -> list[CreditHistoryEntry]:
        return self._run(self._async.get_credit_history(limit=limit, operation=operation))

    def topup_stripe(self, request: StripeTopupRequest) -> StripeTopupResponse:
        return self._run(self._async.topup_stripe(request))

    def get_stripe_topup_status(self, session_id: str) -> StripeTopupStatusResponse:
        return self._run(self._async.get_stripe_topup_status(session_id))

    def get_usdc_topup_requirements(self, amount_usdc: int) -> UsdcTopupRequirements:
        return self._run(self._async.get_usdc_topup_requirements(amount_usdc))

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

    def list_memories(self, *, limit: int = 50) -> list[MemoryEntry]:
        return self._run(self._async.list_memories(limit=limit))

    def create_memory(self, request: StoreMemoryRequest) -> MemoryEntry:
        return self._run(self._async.create_memory(request))

    def delete_memory(self, memory_id: str) -> None:
        return self._run(self._async.delete_memory(memory_id))

    def get_marketplace_catalog(self, **kwargs: Any) -> dict[str, Any]:
        return self._run(self._async.get_marketplace_catalog(**kwargs))

    def set_author_config(self, settlement_wallet: str) -> AuthorConfig:
        return self._run(self._async.set_author_config(settlement_wallet))

    def get_author_config(self) -> AuthorConfig:
        return self._run(self._async.get_author_config())

    def get_marketplace_balance(self) -> dict[str, Any]:
        return self._run(self._async.get_marketplace_balance())

    def get_earnings(self, **kwargs: Any) -> list[EarningsEntry]:
        return self._run(self._async.get_earnings(**kwargs))

    def withdraw(self, request: WithdrawRequest) -> dict[str, Any]:
        return self._run(self._async.withdraw(request))

    def get_withdrawals(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self._run(self._async.get_withdrawals(**kwargs))

    def subscribe(self, qualified_tool_name: str) -> MarketplaceSubscription:
        return self._run(self._async.subscribe(qualified_tool_name))

    def get_subscriptions(self) -> list[MarketplaceSubscription]:
        return self._run(self._async.get_subscriptions())

    def unsubscribe(self, subscription_id: str) -> None:
        return self._run(self._async.unsubscribe(subscription_id))

    # ─── LLM Config ───────────────────────────────────────────────────────────

    def get_llm_config(self) -> OrgLlmConfig:
        return self._run(self._async.get_llm_config())

    def set_llm_config(self, **kwargs: Any) -> OrgLlmConfig:
        return self._run(self._async.set_llm_config(**kwargs))

    def delete_llm_config(self) -> dict[str, Any]:
        return self._run(self._async.delete_llm_config())

    # ─── Models / Benchmarks ──────────────────────────────────────────────────

    def get_model_benchmarks(self) -> ModelBenchmarksResponse:
        return self._run(self._async.get_model_benchmarks())

    def get_org_model_benchmarks(self) -> ModelBenchmarksResponse:
        return self._run(self._async.get_org_model_benchmarks())

    def list_supported_providers(self) -> list[str]:
        return self._async.list_supported_providers()

    def list_models_for_provider(self, provider: str) -> list[str]:
        return self._async.list_models_for_provider(provider)

    # ─── A2A Delegation ───────────────────────────────────────────────────────

    def add_trusted_agent(self, request: AddTrustedAgentRequest) -> TrustedAgent:
        return self._run(self._async.add_trusted_agent(request))

    def list_trusted_agents(self) -> list[TrustedAgent]:
        return self._run(self._async.list_trusted_agents())

    def remove_trusted_agent(self, agent_id: str) -> None:
        return self._run(self._async.remove_trusted_agent(agent_id))

    def get_delegations(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self._run(self._async.get_delegations(**kwargs))

    # ─── Agent Wallets ─────────────────────────────────────────────────────────

    def provision_agent_wallet(self) -> AgentWallet:
        return self._run(self._async.provision_agent_wallet())

    def get_agent_wallet(self, **kwargs: Any) -> AgentWallet:
        return self._run(self._async.get_agent_wallet(**kwargs))

    def deactivate_agent_wallet(self) -> None:
        return self._run(self._async.deactivate_agent_wallet())

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
