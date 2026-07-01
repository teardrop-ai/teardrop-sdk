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
    is_primary: bool = False
    created_at: str = ""

    model_config = {"extra": "allow"}


class AgentWallet(BaseModel):
    """CDP-backed agent wallet provisioned per-org."""

    id: str = ""
    org_id: str = ""
    address: str = ""
    network: str = ""
    is_active: bool = True
    created_at: str = ""

    model_config = {"extra": "allow"}
