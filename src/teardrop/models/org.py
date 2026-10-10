"""Organization credential models."""

from __future__ import annotations

from pydantic import BaseModel, Field, RootModel


class OrgCredentialsEntry(BaseModel):
    """A single M2M credential entry (secret is never returned)."""

    client_id: str
    created_at: str
    disabled_at: str | None = Field(
        default=None, description="ISO 8601 timestamp of disable, or null if active."
    )
    scope: str = Field(default="publish", description="Granted scope: read, publish, or withdraw.")


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
    scope: str = Field(description="Granted scope: read, publish, or withdraw.")
    created_at: str


OrgCredentialRegenerateResponse = RegenerateCredentialsResponse


class OrgCredentialDisableResponse(BaseModel):
    """Response from POST /org/credentials/{client_id}/disable."""

    client_id: str = Field(description="M2M client ID that was disabled.")
    disabled_at: str = Field(description="ISO 8601 timestamp of the disable.")


class OrgSpendingConfigResponse(BaseModel):
    """Response from GET/PATCH /admin/orgs/{org_id}/spending."""

    org_id: str
    balance_usdc: int
    spending_limit_usdc: int
    is_paused: bool
    daily_spend_usdc: int

    model_config = {"extra": "allow"}
