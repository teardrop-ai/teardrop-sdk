"""Organization credential models."""

from __future__ import annotations

from pydantic import BaseModel, RootModel


class OrgCredentialsEntry(BaseModel):
    """A single M2M credential entry (secret is never returned)."""

    client_id: str
    created_at: str


OrgCredentialItem = OrgCredentialsEntry


class OrgCredentialsResponse(RootModel[list[OrgCredentialsEntry]]):
    """Response from GET /org/credentials."""

    @property
    def credentials(self) -> list[OrgCredentialsEntry]:
        """Return the bare-array response under its legacy attribute name."""
        return self.root


class RegenerateCredentialsResponse(BaseModel):
    """Response from POST /org/credentials/regenerate."""

    client_id: str
    client_secret: str
    created_at: str


OrgCredentialRegenerateResponse = RegenerateCredentialsResponse


class OrgSpendingConfigResponse(BaseModel):
    """Response from GET/PATCH /admin/orgs/{org_id}/spending."""

    org_id: str
    balance_usdc: int
    spending_limit_usdc: int
    is_paused: bool
    daily_spend_usdc: int

    model_config = {"extra": "allow"}
