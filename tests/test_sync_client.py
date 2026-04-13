"""Tests for teardrop.client — TeardropClient (sync wrapper)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx

from teardrop.client import TeardropClient
from teardrop.models import BillingBalance, SSEEvent


class TestTeardropClientContextManager:
    def test_enter_exit_does_not_crash(self):
        """Context manager should open and cleanly close the portal."""
        with TeardropClient("http://test", token="tok.en.sig") as client:
            assert client._portal is not None
        assert client._portal is None

    def test_close_without_context_manager(self):
        """close() should work even if __enter__ was never called."""
        client = TeardropClient("http://test", token="tok.en.sig")
        # Portal not yet started — close should be a no-op.
        client.close()
        assert client._portal is None

    def test_portal_started_lazily_on_first_call(self):
        """Portal should be None until _ensure_portal() or first _run() call."""
        client = TeardropClient("http://test", token="tok.en.sig")
        assert client._portal is None
        client._ensure_portal()
        assert client._portal is not None
        client.close()


class TestRunSync:
    def test_run_sync_collects_events(self):
        """run_sync() should return a list of SSEEvents collected from the async stream."""
        expected_events = [
            SSEEvent(type="RUN_STARTED", data={}),
            SSEEvent(type="TEXT_MESSAGE_CONTENT", data={"delta": "hi"}),
            SSEEvent(type="DONE", data={}),
        ]

        async def _fake_run(prompt, **kwargs):
            for e in expected_events:
                yield e

        with TeardropClient("http://test", token="tok.en.sig") as client:
            with patch.object(client._async, "run", side_effect=_fake_run):
                result = client.run_sync("hello")

        assert result == expected_events


class TestSyncDelegation:
    def test_get_balance_delegates(self):
        balance = BillingBalance(org_id="o-1", balance_usdc=9999)

        with TeardropClient("http://test", token="tok.en.sig") as client:
            with patch.object(client._async, "get_balance", new=AsyncMock(return_value=balance)):
                result = client.get_balance()

        assert isinstance(result, BillingBalance)
        assert result.balance_usdc == 9999

    def test_get_me_delegates(self):
        me = {"sub": "user-1", "email": "x@y.com"}

        with TeardropClient("http://test", token="tok.en.sig") as client:
            with patch.object(client._async, "get_me", new=AsyncMock(return_value=me)):
                result = client.get_me()

        assert result["sub"] == "user-1"

    def test_authenticate_siwe_delegates(self):
        async def _fake_siwe(msg, sig, nonce):
            return "jwt.token.here"

        with TeardropClient("http://test", token="tok.en.sig") as client:
            with patch.object(client._async, "authenticate_siwe", side_effect=_fake_siwe):
                result = client.authenticate_siwe("msg", "0xSIG", "nonce-abc")

        assert result == "jwt.token.here"

    def test_get_invoices_delegates(self):
        response = {"items": [], "next_cursor": None}

        with TeardropClient("http://test", token="tok.en.sig") as client:
            with patch.object(client._async, "get_invoices", new=AsyncMock(return_value=response)):
                result = client.get_invoices()

        assert result == response

    def test_get_credit_history_delegates(self):
        response = {"items": [], "next_cursor": None}

        with TeardropClient("http://test", token="tok.en.sig") as client:
            with patch.object(
                client._async, "get_credit_history", new=AsyncMock(return_value=response)
            ):
                result = client.get_credit_history()

        assert result == response

    def test_topup_stripe_delegates(self):
        from teardrop.models import StripeTopupRequest

        async def _fake(request):
            return {"session_id": "sess_x", "checkout_url": "https://stripe.com/pay/x"}

        with TeardropClient("http://test", token="tok.en.sig") as client:
            with patch.object(client._async, "topup_stripe", side_effect=_fake):
                result = client.topup_stripe(
                    StripeTopupRequest(
                        amount_usdc=1_000_000,
                        success_url="https://app.example.com/success",
                        cancel_url="https://app.example.com/cancel",
                    )
                )

        assert "checkout_url" in result


class TestSyncFromAgentCard:
    def test_factory_pre_warms_cache(self):
        """TeardropClient.from_agent_card() returns a client with _agent_card pre-populated."""
        card_data = {"name": "Sync Agent", "url": "http://x", "description": "", "skills": []}
        card_resp = httpx.Response(
            status_code=200,
            content=json.dumps(card_data).encode(),
            headers={"content-type": "application/json"},
            request=httpx.Request("GET", "http://test"),
        )

        with patch("teardrop.client.httpx.AsyncClient") as MockAsyncClient:
            mock_http = AsyncMock()
            mock_http.is_closed = False
            mock_http.get = AsyncMock(return_value=card_resp)
            MockAsyncClient.return_value = mock_http

            client = TeardropClient.from_agent_card("http://test", token="tok.en.sig")
            try:
                assert client._async._agent_card is not None
                assert client._async._agent_card.name == "Sync Agent"
                # Cache is warm — second call must not trigger another HTTP request.
                client.get_agent_card()
                mock_http.get.assert_called_once()
            finally:
                client.close()
