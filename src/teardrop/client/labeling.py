"""Labeling client methods for definitions, predictions, results, and overrides."""

from __future__ import annotations

from typing import TYPE_CHECKING

from teardrop.client._core import _quote_path_segment
from teardrop.models import (
    LabelingBindingRequest,
    LabelingBindingResponse,
    LabelingDefinitionListResponse,
    LabelingOverrideResponse,
    LabelingPredictionListResponse,
    LabelingResultListResponse,
    ScoreResult,
)

if TYPE_CHECKING:
    from teardrop.client._async import AsyncTeardropClient
    from teardrop.client._sync import TeardropClient


class LabelingModule:
    def __init__(self, client: AsyncTeardropClient) -> None:
        self._c = client

    async def get_definitions(self) -> LabelingDefinitionListResponse:
        http = await self._c._get_http()
        resp = await http.get(
            f"{self._c._base_url}/labeling/definitions",
            headers=await self._c._headers(),
        )
        self._c._raise_for_status(resp)
        return LabelingDefinitionListResponse.model_validate(resp.json())

    async def list_definitions(self) -> LabelingDefinitionListResponse:
        return await self.get_definitions()

    async def get_predictions(self, *, limit: int = 50) -> LabelingPredictionListResponse:
        http = await self._c._get_http()
        resp = await http.get(
            f"{self._c._base_url}/labeling/predictions",
            headers=await self._c._headers(),
            params={"limit": limit},
        )
        self._c._raise_for_status(resp)
        return LabelingPredictionListResponse.model_validate(resp.json())

    async def list_predictions(self, *, limit: int = 50) -> LabelingPredictionListResponse:
        return await self.get_predictions(limit=limit)

    async def get_results(self, *, limit: int = 50) -> LabelingResultListResponse:
        http = await self._c._get_http()
        resp = await http.get(
            f"{self._c._base_url}/labeling/results",
            headers=await self._c._headers(),
            params={"limit": limit},
        )
        self._c._raise_for_status(resp)
        return LabelingResultListResponse.model_validate(resp.json())

    async def list_results(self, *, limit: int = 50) -> LabelingResultListResponse:
        return await self.get_results(limit=limit)

    async def bind_definition(
        self,
        request: LabelingBindingRequest,
    ) -> LabelingBindingResponse:
        http = await self._c._get_http()
        resp = await http.post(
            f"{self._c._base_url}/labeling/bindings",
            json=request.model_dump(exclude_none=True),
            headers=await self._c._headers(),
        )
        self._c._raise_for_status(resp)
        return LabelingBindingResponse.model_validate(resp.json())

    async def bind(self, request: LabelingBindingRequest) -> LabelingBindingResponse:
        return await self.bind_definition(request)

    async def override_result(
        self,
        target_id: str,
        request: ScoreResult,
    ) -> LabelingOverrideResponse:
        http = await self._c._get_http()
        resp = await http.post(
            f"{self._c._base_url}/labeling/results/{_quote_path_segment(target_id)}/override",
            json=request.model_dump(exclude_none=True),
            headers=await self._c._headers(),
        )
        self._c._raise_for_status(resp)
        return LabelingOverrideResponse.model_validate(resp.json())


class _SyncLabelingModule:
    def __init__(self, client: TeardropClient) -> None:
        self._c = client

    def get_definitions(self) -> LabelingDefinitionListResponse:
        return self._c._run(self._c._async.labeling.get_definitions())

    def list_definitions(self) -> LabelingDefinitionListResponse:
        return self._c._run(self._c._async.labeling.list_definitions())

    def get_predictions(self, *, limit: int = 50) -> LabelingPredictionListResponse:
        return self._c._run(self._c._async.labeling.get_predictions(limit=limit))

    def list_predictions(self, *, limit: int = 50) -> LabelingPredictionListResponse:
        return self._c._run(self._c._async.labeling.list_predictions(limit=limit))

    def get_results(self, *, limit: int = 50) -> LabelingResultListResponse:
        return self._c._run(self._c._async.labeling.get_results(limit=limit))

    def list_results(self, *, limit: int = 50) -> LabelingResultListResponse:
        return self._c._run(self._c._async.labeling.list_results(limit=limit))

    def bind_definition(self, request: LabelingBindingRequest) -> LabelingBindingResponse:
        return self._c._run(self._c._async.labeling.bind_definition(request))

    def bind(self, request: LabelingBindingRequest) -> LabelingBindingResponse:
        return self._c._run(self._c._async.labeling.bind(request))

    def override_result(self, target_id: str, request: ScoreResult) -> LabelingOverrideResponse:
        return self._c._run(self._c._async.labeling.override_result(target_id, request))
