"""Tests for AsyncTeardropClient billing endpoint methods."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from teardrop.client import AsyncTeardropClient
from teardrop.exceptions import NotFoundError, PaymentRequiredError
from teardrop.models import (
    BillingHistoryEntry,
    Invoice,
    StripeTopupRequest,
    StripeTopupResponse,
    StripeTopupStatusResponse,
    UsdcTopupRequest,
    UsdcTopupRequirements,
)

from .conftest import _json_response


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    return AsyncTeardropClient("http://test", token="tok.en.sig")


@pytest.fixture
def mock_http(client):
    mock = AsyncMock()
    mock.is_closed = False
    client._http = mock
    with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
        yield mock


_BILLING_ENTRY = {
    "run_id": "run-1",
    "user_id": "user-1",
    "amount_usdc": 10000,
    "method": "credit",
    "status": "settled",
    "created_at": "2026-01-01T00:00:00Z",
}

_INVOICE = {
    "run_id": "run-1",
    "tokens_in": 100,
    "tokens_out": 50,
    "tool_calls": 2,
    "total_usdc": 5000,
    "breakdown": [],
    "settled_at": "2026-01-01T00:00:00Z",
}


# ─── get_billing_history ─────────────────────────────────────────────────────


class TestGetBillingHistory:
    async def test_returns_list_of_billing_history_entries(self, client, mock_http):
        mock_http.get.return_value = _json_response([_BILLING_ENTRY, _BILLING_ENTRY])
        result = await client.get_billing_history()
        assert len(result) == 2
        assert isinstance(result[0], BillingHistoryEntry)
        assert result[0].run_id == "run-1"

    async def test_limit_forwarded_as_param(self, client, mock_http):
        mock_http.get.return_value = _json_response([_BILLING_ENTRY])
        await client.get_billing_history(limit=5)
        _, kwargs = mock_http.get.call_args
        assert kwargs["params"] == {"limit": 5}

    async def test_empty_list(self, client, mock_http):
        mock_http.get.return_value = _json_response([])
        result = await client.get_billing_history()
        assert result == []


# ─── get_invoice ─────────────────────────────────────────────────────────────


class TestGetInvoice:
    async def test_returns_invoice(self, client, mock_http):
        mock_http.get.return_value = _json_response(_INVOICE)
        result = await client.get_invoice("run-1")
        assert isinstance(result, Invoice)
        assert result.run_id == "run-1"
        assert result.total_usdc == 5000

    async def test_correct_url(self, client, mock_http):
        mock_http.get.return_value = _json_response(_INVOICE)
        await client.get_invoice("run-abc")
        args, _ = mock_http.get.call_args
        assert args[0] == "http://test/billing/invoice/run-abc"

    async def test_404_raises_not_found(self, client, mock_http):
        mock_http.get.return_value = _json_response({"detail": "Not found"}, status=404)
        with pytest.raises(NotFoundError):
            await client.get_invoice("run-missing")

class TestGetCreditHistoryOperation:
    async def test_operation_param_forwarded(self, client, mock_http):
        mock_http.get.return_value = _json_response([])
        await client.get_credit_history(operation="stripe")
        _, kwargs = mock_http.get.call_args
        assert kwargs["params"]["operation"] == "stripe"

    async def test_no_operation_omits_param(self, client, mock_http):
        mock_http.get.return_value = _json_response([])
        await client.get_credit_history()
        _, kwargs = mock_http.get.call_args
        assert "operation" not in kwargs["params"]

# ─── topup_stripe ─────────────────────────────────────────────────────────────


class TestTopupStripe:
    async def test_returns_stripe_topup_response(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {"client_secret": "cs_test_abc", "session_id": "ses_123"}
        )
        request = StripeTopupRequest(amount_cents=1000, return_url="https://example.com/return")
        result = await client.topup_stripe(request)
        assert isinstance(result, StripeTopupResponse)
        assert result.session_id == "ses_123"
        assert result.client_secret == "cs_test_abc"

    async def test_request_fields_in_body(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {"client_secret": "cs_test_abc", "session_id": "ses_123"}
        )
        request = StripeTopupRequest(amount_cents=2000, return_url="https://example.com/return")
        await client.topup_stripe(request)
        _, kwargs = mock_http.post.call_args
        assert kwargs["json"]["amount_cents"] == 2000
        assert kwargs["json"]["return_url"] == "https://example.com/return"


# ─── get_stripe_topup_status ─────────────────────────────────────────────────


class TestGetStripeTopupStatus:
    async def test_passes_session_id_as_param(self, client, mock_http):
        mock_http.get.return_value = _json_response({"status": "complete"})
        await client.get_stripe_topup_status("ses_123")
        _, kwargs = mock_http.get.call_args
        assert kwargs["params"] == {"session_id": "ses_123"}

    async def test_returns_status_response(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {"status": "complete", "new_balance_fmt": "1.50"}
        )
        result = await client.get_stripe_topup_status("ses_123")
        assert isinstance(result, StripeTopupStatusResponse)
        assert result.status == "complete"
        assert result.new_balance_fmt == "1.50"

    async def test_open_status(self, client, mock_http):
        mock_http.get.return_value = _json_response({"status": "open"})
        result = await client.get_stripe_topup_status("ses_open")
        assert result.status == "open"


# ─── get_usdc_topup_requirements ─────────────────────────────────────────────


class TestGetUsdcTopupRequirements:
    async def test_passes_amount_as_param(self, client, mock_http):
        mock_http.get.return_value = _json_response({"accepts": [], "x402Version": 2})
        await client.get_usdc_topup_requirements(1_000_000)
        _, kwargs = mock_http.get.call_args
        assert kwargs["params"] == {"amount_usdc": 1_000_000}

    async def test_returns_requirements(self, client, mock_http):
        mock_http.get.return_value = _json_response(
            {"accepts": [{"network": "base", "address": "0x..."}], "x402Version": 2}
        )
        result = await client.get_usdc_topup_requirements(1_000_000)
        assert isinstance(result, UsdcTopupRequirements)
        assert result.x402Version == 2
        assert len(result.accepts) == 1


# ─── topup_usdc ───────────────────────────────────────────────────────────────


class TestTopupUsdc:
    async def test_returns_credited_dict(self, client, mock_http):
        mock_http.post.return_value = _json_response({"credited_usdc": 1_000_000})
        request = UsdcTopupRequest(amount_usdc=1_000_000, payment_header="x402-pay-xxx")
        result = await client.topup_usdc(request)
        assert result == {"credited_usdc": 1_000_000}

    async def test_request_fields_in_body(self, client, mock_http):
        mock_http.post.return_value = _json_response({"credited_usdc": 500_000})
        request = UsdcTopupRequest(amount_usdc=500_000, payment_header="hdr")
        await client.topup_usdc(request)
        _, kwargs = mock_http.post.call_args
        assert kwargs["json"]["amount_usdc"] == 500_000
        assert kwargs["json"]["payment_header"] == "hdr"

    async def test_402_raises_payment_required(self, client, mock_http):
        mock_http.post.return_value = _json_response(
            {"error": "Insufficient funds"}, status=402
        )
        request = UsdcTopupRequest(amount_usdc=1, payment_header="hdr")
        with pytest.raises(PaymentRequiredError):
            await client.topup_usdc(request)
