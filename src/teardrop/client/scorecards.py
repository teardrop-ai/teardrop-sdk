"""Public scorecard task, leaderboard, and subject scorecard methods."""

from __future__ import annotations

from typing import TYPE_CHECKING

from teardrop.client._core import _quote_path_segment
from teardrop.models import LeaderboardResponse, ScorecardResponse, ScorecardTaskListResponse

if TYPE_CHECKING:
    from teardrop.client._async import AsyncTeardropClient
    from teardrop.client._sync import TeardropClient


class ScorecardsModule:
    def __init__(self, client: AsyncTeardropClient) -> None:
        self._c = client

    async def list_tasks(self) -> ScorecardTaskListResponse:
        http = await self._c._get_http()
        resp = await http.get(f"{self._c._base_url}/scorecards/tasks")
        self._c._raise_for_status(resp)
        return ScorecardTaskListResponse.model_validate(resp.json())

    async def get_leaderboard(
        self,
        definition_key: str,
        definition_version: int,
        *,
        window_days: int = 90,
    ) -> LeaderboardResponse:
        http = await self._c._get_http()
        resp = await http.get(
            f"{self._c._base_url}/scorecards/{_quote_path_segment(definition_key)}/{definition_version}",
            params={"window_days": window_days},
        )
        self._c._raise_for_status(resp)
        return LeaderboardResponse.model_validate(resp.json())

    async def get_scorecard(
        self,
        definition_key: str,
        definition_version: int,
        subject: str,
        *,
        window_days: int = 90,
    ) -> ScorecardResponse:
        http = await self._c._get_http()
        resp = await http.get(
            f"{self._c._base_url}/scorecards/{_quote_path_segment(definition_key)}/{definition_version}/{_quote_path_segment(subject)}",
            params={"window_days": window_days},
        )
        self._c._raise_for_status(resp)
        return ScorecardResponse.model_validate(resp.json())


class _SyncScorecardsModule:
    def __init__(self, client: TeardropClient) -> None:
        self._c = client

    def list_tasks(self) -> ScorecardTaskListResponse:
        return self._c._run(self._c._async.scorecards.list_tasks())

    def get_leaderboard(
        self,
        definition_key: str,
        definition_version: int,
        *,
        window_days: int = 90,
    ) -> LeaderboardResponse:
        return self._c._run(
            self._c._async.scorecards.get_leaderboard(
                definition_key, definition_version, window_days=window_days
            )
        )

    def get_scorecard(
        self,
        definition_key: str,
        definition_version: int,
        subject: str,
        *,
        window_days: int = 90,
    ) -> ScorecardResponse:
        return self._c._run(
            self._c._async.scorecards.get_scorecard(
                definition_key,
                definition_version,
                subject,
                window_days=window_days,
            )
        )
