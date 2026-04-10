"""Tests for teardrop.client — AsyncTeardropClient."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from teardrop.client import AsyncTeardropClient
from teardrop.exceptions import (
    APIError,
    AuthenticationError,
    PaymentRequiredError,
    RateLimitError,
)
from teardrop.models import BillingBalance, PricingInfo, UsageSummary


def _json_response(body: dict | list, status: int = 200, headers: dict | None = None) -> httpx.Response:
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
        pricing_data = {"rules": [], "model": "claude-sonnet-4-20250514"}
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=_json_response(pricing_data))

        async with AsyncTeardropClient("http://test", token="tok.en.sig") as client:
            client._http = mock_http
            result = await client.get_pricing()

        assert isinstance(result, PricingInfo)


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
