"""Wallet-related models."""

from __future__ import annotations

from pydantic import BaseModel


class LinkWalletRequest(BaseModel):
    siwe_message: str
    siwe_signature: str


class Wallet(BaseModel):
    id: str
    org_id: str = ""
    user_id: str | None = None
    address: str
    chain_id: int
    is_primary: bool
    created_at: str

    model_config = {"extra": "allow"}


WalletItem = Wallet


class LinkWalletResponse(Wallet):
    """Response from POST /wallets/link.

    Spec only guarantees id/address/chain_id; is_primary/created_at may be
    omitted, unlike the full Wallet/WalletItem listing schema.
    """

    is_primary: bool = False
    created_at: str = ""


class AgentWallet(BaseModel):
    """CDP-backed agent wallet provisioned per-org."""

    id: str = ""
    org_id: str = ""
    address: str = ""
    chain_id: int = 0
    wallet_type: str = ""
    network: str = ""
    is_active: bool = True
    balance_usdc: int | None = None
    balance_error: str | None = None
    created_at: str = ""

    model_config = {"extra": "allow"}


class AgentWalletResponse(AgentWallet):
    """Strict response shape for the agent wallet endpoints."""

    id: str
    address: str
    chain_id: int
    wallet_type: str
    is_active: bool
    created_at: str


class AgentWalletDeactivatedResponse(BaseModel):
    """Response from DELETE /wallets/agent."""

    id: str = ""
    status: str
    deactivated_at: str = ""

    model_config = {"extra": "allow"}


class WalletDeletedResponse(BaseModel):
    """Response from DELETE /wallets/{wallet_id}."""

    id: str = ""
    status: str
    deleted_at: str = ""

    model_config = {"extra": "allow"}
