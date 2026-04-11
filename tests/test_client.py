"""Tests for teardrop.client — AsyncTeardropClient."""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from teardrop.client import AsyncTeardropClient
from teardrop.exceptions import (
    APIError,
    AuthenticationError,
    ForbiddenError,
    PaymentRequiredError,
    RateLimitError,
)
from teardrop.models import (
    AgentCard,
    BillingBalance,
    CreditHistoryEntry,
    Invoice,
    PricingInfo,
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

    def test_401_raises_auth_error(self):
        client = AsyncTeardropClient("http://test", token="tok.en.sig")
        resp = _json_response({"detail": "Unauthorized"}, status=401)
        with pytest.raises(AuthenticationError, match="Unauthorized"):
            client._raise_for_status(resp)

    def test_402_raises_payment_error(self):
        client = AsyncTeardropClient("http://test", token="tok.en.sig")
        resp = _json_response({"error": "Insufficient credits"}, status=402)
        with pytest.raises(PaymentRequiredError, match="Insufficient credits"):
            client._raise_for_status(resp)

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
    async def test_run_message_too_long_raises(self):
        """AgentRunRequest enforces max_length=4096 before any HTTP call."""
        from pydantic import ValidationError

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            with pytest.raises(ValidationError):
                async for _ in client.run("x" * 4097):
                    pass

    @pytest.mark.asyncio
    async def test_run_yields_sse_events(self):
        sse_bytes = (
            b"event: RUN_STARTED\ndata: {}\n\n"
            b"event: TEXT_MESSAGE_CONTENT\ndata: {\"delta\": \"hi\"}\n\n"
            b"event: DONE\ndata: {}\n\n"
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
                events = [e async for e in client.run("hello")]

        assert len(events) == 3
        assert events[0].type == "RUN_STARTED"
        assert events[1].type == "TEXT_MESSAGE_CONTENT"
        assert events[1].data["delta"] == "hi"
        assert events[2].type == "DONE"


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
        pricing_data = {"billing_enabled": True}
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(pricing_data))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            result = await client.get_pricing()

        assert isinstance(result, PricingInfo)


class TestGetUsage:
    @pytest.mark.asyncio
    async def test_returns_usage_summary(self):
        usage_data = {"total_runs": 5, "total_tokens_in": 100, "total_tokens_out": 200,
                      "total_tool_calls": 3, "total_duration_ms": 5000}
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
            {"id": "w-1", "address": "0xABC", "chain_id": 8453,
             "user_id": "u-1", "org_id": "o-1"}
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
        card_data = {"name": "Teardrop Agent", "description": "AI agent", "url": "http://x",
                     "skills": [], "unknown_field": "preserved"}
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
    async def test_returns_dict(self):
        me_data = {"sub": "user-1", "email": "a@b.com"}
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(me_data))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                result = await client.get_me()

        assert result["sub"] == "user-1"


class TestGetInvoices:
    @pytest.mark.asyncio
    async def test_validates_items(self):
        invoice_item = {
            "id": "inv-1", "run_id": "run-1", "user_id": "u-1", "org_id": "o-1",
            "tokens_in": 10, "tokens_out": 20, "tool_calls": 1, "cost_usdc": 500,
        }
        response_data = {"items": [invoice_item], "next_cursor": None}
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(response_data))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                result = await client.get_invoices()

        assert len(result["items"]) == 1
        assert isinstance(result["items"][0], Invoice)
        assert result["items"][0].id == "inv-1"


class TestGetCreditHistory:
    @pytest.mark.asyncio
    async def test_validates_items(self):
        entry = {
            "id": "ch-1", "org_id": "o-1", "operation": "topup",
            "amount_usdc": 1000, "balance_usdc_after": 5000,
        }
        response_data = {"items": [entry], "next_cursor": None}
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(response_data))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                result = await client.get_credit_history()

        assert isinstance(result["items"][0], CreditHistoryEntry)
        assert result["items"][0].operation == "topup"


class TestTopupStripe:
    @pytest.mark.asyncio
    async def test_returns_dict(self):
        topup_data = {"checkout_url": "https://stripe.com/pay/xyz"}
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.post = AsyncMock(return_value=_json_response(topup_data))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
                result = await client.topup_stripe(1000, "https://app.example.com/return")

        assert "checkout_url" in result


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

            client = await AsyncTeardropClient.from_agent_card(
                "http://test", token="tok.en.sig"
            )
            try:
                assert client._agent_card is not None
                assert client._agent_card.name == "Teardrop Agent"
                # Second access must be served from cache — no extra HTTP call.
                await client.get_agent_card()
                mock_http.get.assert_called_once()
            finally:
                await client.close()
