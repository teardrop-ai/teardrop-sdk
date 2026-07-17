"""Tests for teardrop.client — TeardropClient (sync wrapper)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx

from teardrop.client import TeardropClient
from teardrop.models import (
    AgentCard,
    BillingBalance,
    CreateEventTriggerRequest,
    CreateScheduleRequest,
    EventTriggerWithSecret,
    ScheduledRun,
    ScheduledRunResult,
    ScheduledRunsPage,
    SSEEvent,
    UsageSummary,
)


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
    def test_get_agent_card_forwards_force_refresh(self):
        card = AgentCard(name="agent")

        with TeardropClient("http://test", token="tok.en.sig") as client:
            with patch.object(
                client._async, "get_agent_card", new=AsyncMock(return_value=card)
            ) as get_agent_card:
                assert client.get_agent_card(force_refresh=True) == card

        get_agent_card.assert_awaited_once_with(force_refresh=True)

    def test_clear_llm_api_key_delegates(self):
        from teardrop.models import LlmConfigResponse

        response = LlmConfigResponse(
            org_id="org-1",
            provider="openai",
            model="gpt-4o",
            has_api_key=False,
            configured=True,
        )

        with TeardropClient("http://test", token="tok.en.sig") as client:
            with patch.object(
                client._async,
                "clear_llm_api_key",
                new=AsyncMock(return_value=response),
            ) as clear_api_key:
                assert client.clear_llm_api_key(provider="openai", model="gpt-4o") == response

        clear_api_key.assert_awaited_once_with(
            provider="openai",
            model="gpt-4o",
            routing_preference="default",
            api_base=None,
            max_tokens=4096,
            temperature=0.0,
            timeout_seconds=120,
        )

    def test_legacy_admin_usage_delegates(self):
        result = UsageSummary(total_runs=1)

        with TeardropClient("http://test", token="tok.en.sig") as client:
            with patch.object(
                client._async, "get_admin_usage_org", new=AsyncMock(return_value=result)
            ) as mock:
                assert client.get_admin_usage_org("org-1", start="2026-01-01") == result
                mock.assert_awaited_once_with("org-1", start="2026-01-01", end=None)

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
        async def _fake_siwe(msg, sig):
            return "jwt.token.here"

        with TeardropClient("http://test", token="tok.en.sig") as client:
            with patch.object(client._async, "authenticate_siwe", side_effect=_fake_siwe):
                result = client.authenticate_siwe("msg", "0xSIG")

        assert result == "jwt.token.here"

    def test_get_invoices_delegates(self):
        response = []

        with TeardropClient("http://test", token="tok.en.sig") as client:
            with patch.object(client._async, "get_invoices", new=AsyncMock(return_value=response)):
                result = client.get_invoices()

        assert result == response

    def test_get_credit_history_delegates(self):
        response = []

        with TeardropClient("http://test", token="tok.en.sig") as client:
            with patch.object(
                client._async, "get_credit_history", new=AsyncMock(return_value=response)
            ):
                result = client.get_credit_history()

        assert result == response

    def test_org_credentials_methods_delegate(self):
        from teardrop.models import OrgCredentialItem, RegenerateCredentialsResponse

        credentials = [OrgCredentialItem(client_id="client-1", created_at="2026-07-17T00:00:00Z")]
        regenerated = RegenerateCredentialsResponse(
            client_id="client-2",
            client_secret="secret-once",
            created_at="2026-07-17T00:00:00Z",
        )

        with TeardropClient("http://test", token="tok.en.sig") as client:
            with (
                patch.object(
                    client._async,
                    "get_org_credentials",
                    new=AsyncMock(return_value=credentials),
                ) as get_credentials,
                patch.object(
                    client._async,
                    "regenerate_org_credentials",
                    new=AsyncMock(return_value=regenerated),
                ) as regenerate_credentials,
            ):
                assert client.get_org_credentials() == credentials
                assert client.regenerate_org_credentials() == regenerated

        get_credentials.assert_awaited_once_with()
        regenerate_credentials.assert_awaited_once_with()

    def test_agent_governance_methods_delegate_with_spec_arguments(self):
        from teardrop.models import (
            AgentDecisionsResponse,
            RunOutcomeRequest,
            RunOutcomeResponse,
            ToolExclusionCreateResponse,
            ToolExclusionRequest,
            ToolExclusionsResponse,
        )

        decisions = AgentDecisionsResponse(items=[])
        outcome = RunOutcomeResponse(status="recorded")
        exclusions = ToolExclusionsResponse(tool_names=["web_search"])
        created = ToolExclusionCreateResponse(status="added", tool_name="web_search")
        request = RunOutcomeRequest(rating=1)
        exclusion_request = ToolExclusionRequest(tool_name="web_search")

        with TeardropClient("http://test", token="tok.en.sig") as client:
            with (
                patch.object(
                    client._async, "get_agent_decisions", new=AsyncMock(return_value=decisions)
                ) as get_decisions,
                patch.object(
                    client._async, "set_run_outcome", new=AsyncMock(return_value=outcome)
                ) as set_outcome,
                patch.object(
                    client._async, "list_tool_exclusions", new=AsyncMock(return_value=exclusions)
                ) as list_exclusions,
                patch.object(
                    client._async,
                    "create_tool_exclusion",
                    new=AsyncMock(return_value=created),
                ) as create_exclusion,
            ):
                assert client.get_agent_decisions(limit=10) == decisions
                assert client.set_run_outcome("run-1", request) == outcome
                assert client.list_tool_exclusions() == exclusions
                assert client.create_tool_exclusion(exclusion_request) == created

        get_decisions.assert_awaited_once_with(limit=10)
        set_outcome.assert_awaited_once_with("run-1", request)
        list_exclusions.assert_awaited_once_with()
        create_exclusion.assert_awaited_once_with(exclusion_request)

    def test_marketplace_contract_methods_forward_required_arguments(self):
        from teardrop.models import (
            MarketplaceImportPreviewResponse,
            MarketplaceImportPublishResponse,
            RunFeedbackResponse,
        )

        feedback = RunFeedbackResponse(
            id="feedback-1",
            run_id="run-1",
            qualified_tool_name="acme/search",
            rating=1,
            created_at="2026-07-17T00:00:00Z",
        )
        preview = MarketplaceImportPreviewResponse(
            server_id="srv-1",
            slots_remaining=1,
            can_publish=True,
            tools=[],
            errors=[],
        )
        published = MarketplaceImportPublishResponse(server_id="srv-1", created=[], errors=[])
        tools = []

        with TeardropClient("http://test", token="tok.en.sig") as client:
            with (
                patch.object(
                    client._async, "submit_feedback", new=AsyncMock(return_value=feedback)
                ) as submit_feedback,
                patch.object(
                    client._async, "import_preview", new=AsyncMock(return_value=preview)
                ) as import_preview,
                patch.object(
                    client._async, "import_publish", new=AsyncMock(return_value=published)
                ) as import_publish,
            ):
                assert (
                    client.submit_feedback(
                        "acme", "search", run_id="run-1", rating=1, comment="Useful"
                    )
                    == feedback
                )
                assert client.import_preview("srv-1", tool_names=["search"]) == preview
                assert client.import_publish("srv-1", tools) == published

        submit_feedback.assert_awaited_once_with(
            "acme", "search", run_id="run-1", rating=1, comment="Useful"
        )
        import_preview.assert_awaited_once_with("srv-1", tool_names=["search"])
        import_publish.assert_awaited_once_with("srv-1", tools)

    def test_topup_stripe_delegates(self):
        from teardrop.models import StripeTopupRequest, StripeTopupResponse

        resp = StripeTopupResponse(client_secret="cs_x", session_id="sess_x")

        with TeardropClient("http://test", token="tok.en.sig") as client:
            with patch.object(client._async, "topup_stripe", new=AsyncMock(return_value=resp)):
                result = client.topup_stripe(
                    StripeTopupRequest(
                        amount_cents=5000,
                        return_url="https://app.example.com/return",
                    )
                )

        assert result.session_id == "sess_x"

    def test_schedules_namespace_delegates(self):
        schedule = ScheduledRun(
            id="sched-1",
            org_id="org-1",
            user_id="user-1",
            name="Daily Summary",
            prompt="Summarize balances",
            schedule_kind="interval",
            interval_seconds=86400,
            enabled=True,
            next_run_at=None,
            consecutive_failures=0,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )

        with TeardropClient("http://test", token="tok.en.sig") as client:
            with patch.object(
                client._async.schedules,
                "create",
                new=AsyncMock(return_value=schedule),
            ):
                result = client.schedules.create(
                    CreateScheduleRequest(
                        name="Daily Summary",
                        prompt="Summarize balances",
                        interval_seconds=86400,
                    )
                )

        assert result.id == "sched-1"

    def test_event_triggers_namespace_delegates(self):
        trigger = EventTriggerWithSecret(
            id="evt-1",
            org_id="org-1",
            user_id="user-1",
            name="On Payment",
            prompt="Audit {{event_json}}",
            schedule_kind="event",
            enabled=True,
            trigger_token="tok-1",
            event_path="/agent/events/tok-1",
            secret="secret-1",
            consecutive_failures=0,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )

        with TeardropClient("http://test", token="tok.en.sig") as client:
            with patch.object(
                client._async.event_triggers,
                "create",
                new=AsyncMock(return_value=trigger),
            ):
                result = client.event_triggers.create(
                    CreateEventTriggerRequest(
                        name="On Payment",
                        prompt="Audit {{event_json}}",
                    )
                )

        assert result.secret == "secret-1"

    def test_schedules_runs_iter_auto_paginates(self):
        page_1 = ScheduledRunsPage(
            items=[
                ScheduledRunResult(
                    id="run-1",
                    schedule_id="sched-1",
                    org_id="org-1",
                    run_id="core-run-1",
                    status="completed",
                    cost_usdc=0,
                    created_at="2026-01-01T00:00:00Z",
                )
            ],
            next_cursor="page-2",
        )
        page_2 = ScheduledRunsPage(
            items=[
                ScheduledRunResult(
                    id="run-2",
                    schedule_id="sched-1",
                    org_id="org-1",
                    run_id="core-run-2",
                    status="completed",
                    cost_usdc=0,
                    created_at="2026-01-01T00:00:00Z",
                )
            ],
            next_cursor=None,
        )

        with TeardropClient("http://test", token="tok.en.sig") as client:
            with patch.object(
                client._async.schedules,
                "runs",
                new=AsyncMock(side_effect=[page_1, page_2]),
            ) as runs_mock:
                result = list(client.schedules.runs_iter("sched-1", limit=1))

        assert [item.id for item in result] == ["run-1", "run-2"]
        assert runs_mock.call_args_list[0].kwargs == {"limit": 1, "cursor": None}
        assert runs_mock.call_args_list[1].kwargs == {"limit": 1, "cursor": "page-2"}

    def test_event_triggers_runs_iter_auto_paginates(self):
        page_1 = ScheduledRunsPage(
            items=[
                ScheduledRunResult(
                    id="run-1",
                    schedule_id="evt-1",
                    org_id="org-1",
                    run_id="event-run-1",
                    status="completed",
                    cost_usdc=0,
                    created_at="2026-01-01T00:00:00Z",
                )
            ],
            next_cursor="page-2",
        )
        page_2 = ScheduledRunsPage(
            items=[
                ScheduledRunResult(
                    id="run-2",
                    schedule_id="evt-1",
                    org_id="org-1",
                    run_id="event-run-2",
                    status="completed",
                    cost_usdc=0,
                    created_at="2026-01-01T00:00:00Z",
                )
            ],
            next_cursor=None,
        )

        with TeardropClient("http://test", token="tok.en.sig") as client:
            with patch.object(
                client._async.event_triggers,
                "runs",
                new=AsyncMock(side_effect=[page_1, page_2]),
            ) as runs_mock:
                result = list(client.event_triggers.runs_iter("evt-1", limit=1))

        assert [item.id for item in result] == ["run-1", "run-2"]
        assert runs_mock.call_args_list[0].kwargs == {"limit": 1, "cursor": None}
        assert runs_mock.call_args_list[1].kwargs == {"limit": 1, "cursor": "page-2"}


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
