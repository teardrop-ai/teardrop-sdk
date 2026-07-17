"""Tests for teardrop.client — AsyncTeardropClient."""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from teardrop.client import AsyncTeardropClient, _parse_list_response
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
    BillingBalance,
    BillingHistoryEntry,
    BillingPricingResponse,
    CreditHistoryEntry,
    Invoice,
    UsageSummary,
    Wallet,
)


def _json_response(
    body: dict | list, status: int = 200, headers: dict | None = None
) -> httpx.Response:
    """Build a fake httpx.Response with JSON body."""
    resp = httpx.Response(
        status_code=status,
        content=json.dumps(body).encode(),
        headers={"content-type": "application/json", **(headers or {})},
        request=httpx.Request("GET", "http://test"),
    )
    return resp


class TestRaiseForStatus:
    def test_success_no_raise(self):
        client = AsyncTeardropClient("http://test", token="tok.en.sig")
        resp = _json_response({"ok": True}, status=200)
        client._raise_for_status(resp)  # Should not raise

    def test_non_json_body_falls_back_to_text(self):
        """When the error response has no JSON body, body is set to the raw text."""
        client = AsyncTeardropClient("http://test", token="tok.en.sig")
        resp = httpx.Response(
            status_code=500,
            content=b"Internal Server Error",
            headers={"content-type": "text/plain"},
            request=httpx.Request("GET", "http://test"),
        )
        from teardrop.exceptions import APIError

        with pytest.raises(APIError) as exc_info:
            client._raise_for_status(resp)
        # body attribute should contain the raw response text
        assert exc_info.value.body == "Internal Server Error"

    def test_401_raises_auth_error(self):
        client = AsyncTeardropClient("http://test", token="tok.en.sig")
        resp = _json_response({"detail": "Unauthorized"}, status=401)
        with pytest.raises(AuthenticationError, match="Unauthorized"):
            client._raise_for_status(resp)

    def test_402_raises_payment_error(self):
        client = AsyncTeardropClient("http://test", token="tok.en.sig")
        resp = _json_response(
            {"error": "Insufficient credits", "accepts": [{"method": "usdc"}]},
            status=402,
            headers={"X-PAYMENT-REQUIRED": "req_123"},
        )
        with pytest.raises(PaymentRequiredError) as exc_info:
            client._raise_for_status(resp)
        assert exc_info.value.detail == "Insufficient credits"
        assert exc_info.value.payment_header == "req_123"
        assert exc_info.value.requirements["accepts"][0]["method"] == "usdc"

    def test_403_raises_forbidden_error(self):
        client = AsyncTeardropClient("http://test", token="tok.en.sig")
        resp = _json_response({"detail": "You do not have permission"}, status=403)
        with pytest.raises(ForbiddenError, match="You do not have permission"):
            client._raise_for_status(resp)

    def test_403_default_detail(self):
        client = AsyncTeardropClient("http://test", token="tok.en.sig")
        resp = _json_response({"error": "other"}, status=403)
        with pytest.raises(ForbiddenError, match="Forbidden"):
            client._raise_for_status(resp)

    def test_429_raises_rate_limit_error(self):
        client = AsyncTeardropClient("http://test", token="tok.en.sig")
        resp = _json_response(
            {"detail": "Rate limit exceeded"},
            status=429,
            headers={"Retry-After": "30"},
        )
        with pytest.raises(RateLimitError) as exc_info:
            client._raise_for_status(resp)
        assert exc_info.value.retry_after == 30

    def test_500_raises_api_error(self):
        client = AsyncTeardropClient("http://test", token="tok.en.sig")
        resp = _json_response({"error": "internal"}, status=500)
        with pytest.raises(APIError) as exc_info:
            client._raise_for_status(resp)
        assert exc_info.value.status_code == 500


class TestRun:
    @pytest.mark.asyncio
    async def test_run_with_usage_date_params(self):
        """get_usage forwards optional start/end params."""
        from unittest.mock import AsyncMock, patch

        from teardrop.models import UsageSummary

        client = AsyncTeardropClient("http://test", token="tok.en.sig")
        mock = AsyncMock()
        mock.is_closed = False
        mock.get.return_value = _json_response(
            {
                "total_runs": 0,
                "total_tokens_in": 0,
                "total_tokens_out": 0,
                "total_tool_calls": 0,
                "total_duration_ms": 0,
            }
        )
        client._http = mock
        with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
            result = await client.get_usage(start="2026-01-01", end="2026-01-31")
        assert isinstance(result, UsageSummary)
        _, kwargs = mock.get.call_args
        assert kwargs["params"]["start"] == "2026-01-01"
        assert kwargs["params"]["end"] == "2026-01-31"

    @pytest.mark.asyncio
    async def test_run_message_too_long_raises(self):
        """AgentRunRequest enforces max_length=4096 before any HTTP call."""
        from pydantic import ValidationError

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            with pytest.raises(ValidationError):
                async for _ in client.run("x" * 4097):
                    pass

    @pytest.mark.asyncio
    async def test_run_yields_sse_events(self):
        import json

        def _ev(event, data=None):
            return json.dumps({"event": event, "data": data or {}}).encode()

        sse_bytes = (
            b"data: "
            + _ev("RUN_STARTED")
            + b"\n\n"
            + b"data: "
            + _ev("TEXT_MESSAGE_CONTENT", {"delta": "hi"})
            + b"\n\n"
            + b"data: "
            + _ev("DONE")
            + b"\n\n"
        )

        async def _aiter_lines():
            for line in sse_bytes.decode().splitlines():
                yield line
            yield ""  # final blank

        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.aiter_lines = _aiter_lines
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.stream = MagicMock(return_value=mock_resp)

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                events = [e async for e in client.run("hello", emit_ui=False)]

        assert len(events) == 3
        assert events[0].type == "RUN_STARTED"
        assert events[1].type == "TEXT_MESSAGE_CONTENT"
        assert events[1].data["delta"] == "hi"
        assert events[2].type == "DONE"

        # Verify emit_ui was passed in request body
        args, kwargs = mock_http.stream.call_args
        assert kwargs["json"]["emit_ui"] is False


class TestGetBalance:
    @pytest.mark.asyncio
    async def test_returns_billing_balance(self):
        balance_data = {"org_id": "org-1", "balance_usdc": 50000}
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(balance_data))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                result = await client.get_balance()

        assert isinstance(result, BillingBalance)


class TestGetPricing:
    @pytest.mark.asyncio
    async def test_returns_pricing_info(self):
        pricing_data = {"tools": [], "base_cost_usdc": 1000, "updated_at": "2026-01-01T00:00:00Z"}
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(pricing_data))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            result = await client.get_pricing()

        assert isinstance(result, BillingPricingResponse)


class TestGetUsage:
    @pytest.mark.asyncio
    async def test_returns_usage_summary(self):
        usage_data = {
            "total_runs": 5,
            "total_tokens_in": 100,
            "total_tokens_out": 200,
            "total_tool_calls": 3,
            "total_duration_ms": 12000,
        }
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(usage_data))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                result = await client.get_usage()

        assert isinstance(result, UsageSummary)
        assert result.total_runs == 5


class TestGetWallets:
    @pytest.mark.asyncio
    async def test_returns_wallet_list(self):
        wallets_data = [
            {
                "id": "w-1",
                "address": "0xABC",
                "chain_id": 8453,
                "user_id": "u-1",
                "is_primary": False,
                "created_at": "2026-01-01T00:00:00Z",
            }
        ]
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(wallets_data))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                result = await client.get_wallets()

        assert len(result) == 1
        assert isinstance(result[0], Wallet)
        assert result[0].address == "0xABC"


class TestGetAgentCard:
    @pytest.mark.asyncio
    async def test_returns_agent_card(self):
        card_data = {
            "name": "Teardrop Agent",
            "description": "AI agent",
            "url": "http://x",
            "skills": [],
            "unknown_field": "preserved",
        }
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(card_data))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            result = await client.get_agent_card()

        assert isinstance(result, AgentCard)
        assert result.name == "Teardrop Agent"


class TestGetMe:
    @pytest.mark.asyncio
    async def test_returns_jwt_payload(self):
        from teardrop.models import JwtPayloadBase

        me_data = {
            "sub": "user-1",
            "org_id": "org-1",
            "role": "member",
            "auth_method": "email",
            "email": "a@b.com",
            "exp": 9999999999,
            "iat": 1000000000,
        }
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(me_data))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                result = await client.get_me()

        assert isinstance(result, JwtPayloadBase)
        assert result.sub == "user-1"


class TestGetInvoices:
    @pytest.mark.asyncio
    async def test_validates_items(self):
        invoice_item = {
            "run_id": "run-1",
            "tokens_in": 10,
            "tokens_out": 20,
            "tool_calls": 1,
            "total_usdc": 500,
            "breakdown": [],
            "settled_at": "2026-01-01T00:00:00Z",
        }
        response_data = {"items": [invoice_item], "next_cursor": None}
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(response_data))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                result = await client.get_invoices()

        assert len(result) == 1
        assert isinstance(result[0], Invoice)
        assert result[0].run_id == "run-1"


class TestGetCreditHistory:
    @pytest.mark.asyncio
    async def test_validates_items(self):
        entry = {
            "id": "ch-1",
            "amount_usdc": 1000,
            "operation": "topup",
            "balance_usdc_after": 500_000,
            "reason": None,
            "created_at": "2026-01-01T00:00:00Z",
        }
        response_data = [entry]
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(response_data))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                result = await client.get_credit_history()

        assert isinstance(result[0], CreditHistoryEntry)
        assert result[0].operation == "topup"
        assert result[0].balance_usdc_after == 500_000


class TestTopupStripe:
    @pytest.mark.asyncio
    async def test_returns_stripe_response(self):
        from teardrop.models import StripeTopupRequest, StripeTopupResponse

        topup_data = {"client_secret": "cs_abc", "session_id": "sess_abc"}
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.post = AsyncMock(return_value=_json_response(topup_data))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                result = await client.topup_stripe(
                    StripeTopupRequest(
                        amount_cents=5000,
                        return_url="https://app.example.com/return",
                    )
                )

        assert isinstance(result, StripeTopupResponse)
        assert result.session_id == "sess_abc"


class TestContextManager:
    @pytest.mark.asyncio
    async def test_close_called_on_exit(self):
        client = AsyncTeardropClient("http://test", token="tok.en.sig")
        mock_http = AsyncMock()
        mock_http.is_closed = False
        client._http = mock_http

        async with client:
            pass  # __aexit__ should call close()

        mock_http.aclose.assert_awaited_once()


class TestGetAgentCardCached:
    """Tests for TTL caching, security hardening, and force_refresh on get_agent_card()."""

    @pytest.mark.asyncio
    async def test_cache_hit_no_extra_http_call(self):
        """Second call returns cached result without a second HTTP request."""
        card_data = {"name": "Teardrop Agent", "url": "http://x", "skills": []}
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(card_data))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            first = await client.get_agent_card()
            second = await client.get_agent_card()

        assert first is second
        mock_http.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_ttl_expiry_refetches(self):
        """After TTL expires the next call issues a fresh HTTP request."""
        card_data = {"name": "Teardrop Agent", "url": "http://x"}
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(card_data))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            await client.get_agent_card()
            # Push the fetch timestamp past the TTL window.
            client._agent_card_fetched_at = time.time() - 400
            await client.get_agent_card()

        assert mock_http.get.call_count == 2

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_warm_cache(self):
        """force_refresh=True fetches unconditionally even when cache is valid."""
        card_data = {"name": "Teardrop Agent", "url": "http://x"}
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(card_data))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            await client.get_agent_card()
            await client.get_agent_card(force_refresh=True)

        assert mock_http.get.call_count == 2

    @pytest.mark.asyncio
    async def test_size_cap_raises_api_error(self):
        """Responses larger than 64 KB raise APIError."""
        oversized_resp = httpx.Response(
            status_code=200,
            content=b"x" * 65537,
            headers={"content-type": "application/json"},
            request=httpx.Request("GET", "http://test"),
        )
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=oversized_resp)

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with pytest.raises(APIError):
                await client.get_agent_card()

    @pytest.mark.asyncio
    async def test_wrong_content_type_raises_api_error(self):
        """A non-JSON Content-Type raises APIError."""
        html_resp = httpx.Response(
            status_code=200,
            content=b"<html>Not JSON</html>",
            headers={"content-type": "text/html; charset=utf-8"},
            request=httpx.Request("GET", "http://test"),
        )
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=html_resp)

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with pytest.raises(APIError):
                await client.get_agent_card()


class TestFromAgentCard:
    @pytest.mark.asyncio
    async def test_factory_pre_warms_cache(self):
        """from_agent_card() returns a client with _agent_card already populated."""
        card_data = {"name": "Teardrop Agent", "url": "http://x", "skills": []}

        with patch("teardrop.client.httpx.AsyncClient") as MockAsyncClient:
            mock_http = AsyncMock()
            mock_http.is_closed = False
            mock_http.get = AsyncMock(return_value=_json_response(card_data))
            MockAsyncClient.return_value = mock_http

            client = await AsyncTeardropClient.from_agent_card("http://test", token="tok.en.sig")
            try:
                assert client._agent_card is not None
                assert client._agent_card.name == "Teardrop Agent"
                # Second access must be served from cache — no extra HTTP call.
                await client.get_agent_card()
                mock_http.get.assert_called_once()
            finally:
                await client.close()


class TestTransportErrors:
    """Verify that httpx transport errors are wrapped into TeardropError."""

    @pytest.mark.asyncio
    async def test_connect_error_raises_teardrop_error(self, client, mock_http):
        mock_http.get.side_effect = httpx.ConnectError("refused")
        with pytest.raises(TeardropError, match="Connection failed"):
            await client.get_me()

    @pytest.mark.asyncio
    async def test_timeout_error_raises_teardrop_error(self, client, mock_http):
        mock_http.get.side_effect = httpx.TimeoutException("timed out")
        with pytest.raises(TeardropError, match="Request timed out"):
            await client.get_me()

    @pytest.mark.asyncio
    async def test_connect_error_on_post_raises_teardrop_error(self, client, mock_http):
        mock_http.post.side_effect = httpx.ConnectError("refused")
        with pytest.raises(TeardropError, match="Connection failed"):
            from teardrop.models import StoreMemoryRequest

            await client.create_memory(StoreMemoryRequest(content="test"))


class TestGetAgentTools:
    """Tests for client.get_agent_tools()."""

    @pytest.mark.asyncio
    async def test_returns_list_of_agent_tools(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {
                "tools": [
                    {
                        "name": "platform/web_search",
                        "source": "platform",
                        "access_mode": "included",
                    },
                    {"name": "acme/my_tool", "source": "marketplace", "access_mode": "subscribed"},
                ]
            }
        )
        result = await client.get_agent_tools()
        assert len(result) == 2
        assert result[0].name == "platform/web_search"
        assert result[0].source == "platform"
        assert result[0].access_mode == "included"
        assert result[1].source == "marketplace"
        assert result[1].access_mode == "subscribed"

    @pytest.mark.asyncio
    async def test_hits_agent_tools_endpoint(self, client, mock_http):
        mock_http.get.return_value = _json_response({"tools": []})
        await client.get_agent_tools()
        args, kwargs = mock_http.get.call_args
        assert args[0] == "http://test/agent/tools"
        assert "headers" in kwargs

    @pytest.mark.asyncio
    async def test_empty_list(self, client, mock_http):
        mock_http.get.return_value = _json_response({"tools": []})
        result = await client.get_agent_tools()
        assert result == []


class TestToolExclusions:
    """Tests for client.list_tool_exclusions()/create_tool_exclusion()/delete_tool_exclusion()."""

    @pytest.mark.asyncio
    async def test_list_returns_response_model(self, client, mock_http):
        from teardrop.models import ToolExclusionsResponse

        mock_http.get.return_value = _json_response({"tool_names": ["web_search", "web_scrape"]})
        result = await client.list_tool_exclusions()
        assert isinstance(result, ToolExclusionsResponse)
        assert result.tool_names == ["web_search", "web_scrape"]

    @pytest.mark.asyncio
    async def test_create_returns_response_model_and_sends_body(self, client, mock_http):
        from teardrop.models import ToolExclusionCreateResponse, ToolExclusionRequest

        mock_http.post.return_value = _json_response({"status": "added", "tool_name": "web_search"})
        result = await client.create_tool_exclusion(ToolExclusionRequest(tool_name="web_search"))
        assert isinstance(result, ToolExclusionCreateResponse)
        assert result.status == "added"
        assert result.tool_name == "web_search"

        args, kwargs = mock_http.post.call_args
        assert args[0] == "http://test/agent/tool-exclusions"
        assert kwargs["json"] == {"tool_name": "web_search"}

    @pytest.mark.asyncio
    async def test_delete_calls_expected_url(self, client, mock_http):
        mock_http.delete.return_value = _json_response({})
        result = await client.delete_tool_exclusion("web_search")
        assert result is None
        args, _ = mock_http.delete.call_args
        assert args[0] == "http://test/agent/tool-exclusions/web_search"


class TestAgentDecisionsAndOutcome:
    """Tests for client.get_agent_decisions()/set_run_outcome()."""

    @pytest.mark.asyncio
    async def test_get_agent_decisions_parses_response(self, client, mock_http):
        from teardrop.models import AgentDecisionsResponse

        mock_http.get.return_value = _json_response(
            {
                "items": [
                    {
                        "id": "dec-abc",
                        "run_id": "run-xyz",
                        "task_class": "research_summary",
                        "action": "execute_tool",
                        "reasoning": "Determined that search results are needed to answer.",
                        "confidence": 0.94,
                        "tool_names": ["web_search"],
                        "outcome": 1,
                        "outcome_source": "feedback",
                        "created_at": "2026-07-16T12:00:00.000000",
                    }
                ],
                "next_cursor": "2026-07-16T12:00:00.000000",
            }
        )
        result = await client.get_agent_decisions(limit=10, cursor="abc")
        assert isinstance(result, AgentDecisionsResponse)
        assert result.items[0].id == "dec-abc"
        assert result.items[0].confidence == 0.94
        assert result.next_cursor == "2026-07-16T12:00:00.000000"

        args, kwargs = mock_http.get.call_args
        assert args[0] == "http://test/agent/decisions"
        assert kwargs["params"] == {"limit": 10, "cursor": "abc"}

    @pytest.mark.asyncio
    async def test_set_run_outcome_sends_rating(self, client, mock_http):
        from teardrop.models import RunOutcomeRequest

        mock_http.patch.return_value = _json_response({"run_id": "run-1", "rating": 1})
        await client.set_run_outcome("run-1", RunOutcomeRequest(rating=1))
        args, kwargs = mock_http.patch.call_args
        assert args[0] == "http://test/agent/runs/run-1/outcome"
        assert kwargs["json"] == {"rating": 1}

    @pytest.mark.asyncio
    async def test_set_run_outcome_404_raises_not_found(self, client, mock_http):
        from teardrop.exceptions import NotFoundError
        from teardrop.models import RunOutcomeRequest

        mock_http.patch.return_value = _json_response({"detail": "Already labeled"}, status=404)
        with pytest.raises(NotFoundError):
            await client.set_run_outcome("run-1", RunOutcomeRequest(rating=1))


class TestRunWithToolPolicy:
    """Tests that tool_policy is serialized into the agent run request."""

    @pytest.mark.asyncio
    async def test_tool_policy_included_in_body(self, client, mock_http):
        from teardrop.models import ToolPolicy

        async def _aiter_lines():
            yield 'data: {"event": "DONE", "data": {}}'
            yield ""

        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.aiter_lines = _aiter_lines
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_http.stream = MagicMock(return_value=mock_resp)

        policy = ToolPolicy(exclude_names=["platform/web_search"])
        events = []
        async for event in client.run("hello", tool_policy=policy):
            events.append(event)

        _, kwargs = mock_http.stream.call_args
        body = kwargs["json"]
        assert body["tool_policy"] == {"exclude_names": ["platform/web_search"]}

    @pytest.mark.asyncio
    async def test_tool_policy_omitted_when_none(self, client, mock_http):
        """When tool_policy is None, exclude_none should leave it out of the body."""

        async def _aiter_lines():
            yield 'data: {"event": "DONE", "data": {}}'
            yield ""

        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.aiter_lines = _aiter_lines
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_http.stream = MagicMock(return_value=mock_resp)

        events = []
        async for event in client.run("hello"):
            events.append(event)

        _, kwargs = mock_http.stream.call_args
        assert "tool_policy" not in kwargs["json"]


class TestParseListResponse:
    """Tests for the _parse_list_response private helper."""

    def test_bare_array(self):
        from teardrop.models import BillingHistoryEntry

        data = [
            {
                "run_id": "r-1",
                "user_id": "u-1",
                "amount_usdc": 100,
                "method": "credit",
                "status": "settled",
                "created_at": "2026-01-01T00:00:00Z",
            },
        ]
        result = _parse_list_response(data, BillingHistoryEntry)
        assert len(result) == 1
        assert result[0].run_id == "r-1"

    def test_envelope_items(self):
        from teardrop.models import BillingHistoryEntry

        data = {
            "items": [
                {
                    "run_id": "r-1",
                    "user_id": "u-1",
                    "amount_usdc": 100,
                    "method": "credit",
                    "status": "settled",
                    "created_at": "2026-01-01T00:00:00Z",
                },
            ],
            "next_cursor": None,
        }
        result = _parse_list_response(data, BillingHistoryEntry, item_container="items")
        assert len(result) == 1
        assert result[0].run_id == "r-1"

    def test_envelope_tools(self):
        from teardrop.models import AgentTool

        data = {"tools": [{"name": "t1", "source": "platform", "access_mode": "included"}]}
        result = _parse_list_response(data, AgentTool, item_container="tools")
        assert len(result) == 1
        assert result[0].name == "t1"

    def test_empty_bare_array(self):
        result = _parse_list_response([], BillingHistoryEntry)
        assert result == []

    def test_empty_envelope(self):
        result = _parse_list_response({"items": []}, BillingHistoryEntry, item_container="items")
        assert result == []

    def test_missing_field_in_envelope(self):
        result = _parse_list_response({"other": []}, BillingHistoryEntry, item_container="items")
        assert result == []

    def test_envelope_auto_keys(self):
        from teardrop.models import AgentTool

        data = {"tools": [{"name": "t1", "source": "platform", "access_mode": "included"}]}
        result = _parse_list_response(data, AgentTool)
        assert len(result) == 1
        assert result[0].name == "t1"

    def test_non_dict_non_list(self):
        import pytest
        from pydantic_core import ValidationError

        with pytest.raises(ValidationError):
            _parse_list_response("not a list", BillingHistoryEntry)
