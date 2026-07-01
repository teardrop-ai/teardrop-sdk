"""Shared client core, transport helpers, and module-level constants."""

from __future__ import annotations

import contextlib
from typing import Any, AsyncIterator, TypeVar

import anyio
import httpx
from pydantic import BaseModel

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
    AgentCard,
    ModelBenchmarksResponse,
    OrgLlmConfig,
    ScheduledRunResult,
    ScheduledRunsPage,
)

_UNSET: object = object()
_AGENT_CARD_TTL: int = 300
_AGENT_CARD_MAX_BYTES: int = 65_536
_LLM_CONFIG_TTL: int = 300
_MODEL_BENCHMARKS_TTL: int = 600

_T = TypeVar("_T", bound=BaseModel)


def _parse_list_response(
    data: Any,
    item_model: type[_T],
    item_container: str | None = None,
) -> list[_T]:
    """Parse a list response supporting both bare-array and envelope shapes."""
    envelope_keys = ["items", "tools", "subscriptions", "mcp_servers", "servers", "earnings"]
    if isinstance(data, dict):
        if item_container is not None:
            items = data.get(item_container, [])
        else:
            items = []
            for key in envelope_keys:
                if key in data:
                    items = data[key]
                    break
        return [item_model.model_validate(x) for x in items]
    return [item_model.model_validate(x) for x in data]


def _parse_scheduled_runs_page(data: Any) -> ScheduledRunsPage:
    if isinstance(data, list):
        return ScheduledRunsPage(
            items=[ScheduledRunResult.model_validate(item) for item in data],
            next_cursor=None,
        )
    items = data.get("items", []) if isinstance(data, dict) else []
    next_cursor = data.get("next_cursor") if isinstance(data, dict) else None
    return ScheduledRunsPage(
        items=[ScheduledRunResult.model_validate(item) for item in items],
        next_cursor=next_cursor,
    )


class _HttpProxy:
    """Wraps httpx.AsyncClient to translate transport errors into TeardropError."""

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
    async def stream(self, method: str, url: str, **kw: Any) -> AsyncIterator[httpx.Response]:
        try:
            async with self._c.stream(method, url, **kw) as resp:
                yield resp
        except httpx.ConnectError as exc:
            raise TeardropError(f"Connection failed: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise TeardropError(f"Request timed out: {exc}") from exc


class _AsyncClientBase:
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
        self._agent_card: AgentCard | None = None
        self._agent_card_fetched_at: float = 0.0
        self._agent_card_lock: anyio.Lock = anyio.Lock()
        self._llm_config_cache: tuple[OrgLlmConfig, float] | None = None
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
            raise PaymentRequiredError(detail, requirements=reqs, payment_header=payment_header)
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

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()
