"""Billing client methods."""

from __future__ import annotations

from typing import Any, Literal

from teardrop.models import (
    BillingBalance,
    BillingHistoryEntry,
    BillingPricingResponse,
    CreditHistoryResponse,
    Invoice,
    InvoiceListResponse,
    StripeSessionStatusResponse,
    StripeTopupRequest,
    StripeTopupResponse,
    UsdcTopupRequest,
    UsdcTopupRequirementsResponse,
    UsdcTopupResponse,
)


class _BillingMixin:
    async def get_balance(self) -> BillingBalance:
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/billing/balance", headers=await self._headers())
        self._raise_for_status(resp)
        return BillingBalance.model_validate(resp.json())

    async def get_pricing(self) -> BillingPricingResponse:
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/billing/pricing")
        self._raise_for_status(resp)
        return BillingPricingResponse.model_validate(resp.json())

    async def get_billing_history(self, *, limit: int = 20) -> list[BillingHistoryEntry]:
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        resp = await http.get(
            f"{self._base_url}/billing/history",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        data = resp.json()
        if isinstance(data, list):
            return [BillingHistoryEntry.model_validate(item) for item in data]
        return [BillingHistoryEntry.model_validate(item) for item in data.get("items", [])]

    async def get_invoices(self, *, limit: int = 20) -> InvoiceListResponse:
        http = await self._get_http()
        params: dict[str, Any] = {"limit": limit}
        resp = await http.get(
            f"{self._base_url}/billing/invoices",
            headers=await self._headers(),
            params=params,
        )
        self._raise_for_status(resp)
        return InvoiceListResponse.model_validate(resp.json())

    async def get_invoice(self, run_id: str) -> Invoice:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/billing/invoice/{run_id}",
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return Invoice.model_validate(resp.json())

    async def get_credit_history(
        self, *, limit: int = 20, operation: Literal["debit", "topup"] | None = None
    ) -> CreditHistoryResponse:
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
        return CreditHistoryResponse.model_validate(resp.json())

    async def topup_stripe(self, request: StripeTopupRequest) -> StripeTopupResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/billing/topup/stripe",
            json=request.model_dump(),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return StripeTopupResponse.model_validate(resp.json())

    async def get_stripe_topup_status(self, session_id: str) -> StripeSessionStatusResponse:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/billing/topup/stripe/status",
            headers=await self._headers(),
            params={"session_id": session_id},
        )
        self._raise_for_status(resp)
        return StripeSessionStatusResponse.model_validate(resp.json())

    async def get_usdc_topup_requirements(self, amount_usdc: int) -> UsdcTopupRequirementsResponse:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/billing/topup/usdc/requirements",
            headers=await self._headers(),
            params={"amount_usdc": amount_usdc},
        )
        self._raise_for_status(resp)
        return UsdcTopupRequirementsResponse.model_validate(resp.json())

    async def topup_usdc(self, request: UsdcTopupRequest) -> UsdcTopupResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/billing/topup/usdc",
            json=request.model_dump(exclude_none=True),
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return UsdcTopupResponse.model_validate(resp.json())
