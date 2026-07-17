"""Organization credential models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OrgCredentialsEntry(BaseModel):
    """A single M2M credential entry (secret is never returned)."""

    client_id: str
    created_at: str = ""


OrgCredentialItem = OrgCredentialsEntry


class OrgCredentialsResponse(BaseModel):
    """Response from GET /org/credentials."""

    credentials: list[OrgCredentialsEntry] = Field(default_factory=list)


class RegenerateCredentialsResponse(BaseModel):
    """Response from POST /org/credentials/regenerate."""

    client_id: str
    client_secret: str
    created_at: str = ""


OrgCredentialRegenerateResponse = RegenerateCredentialsResponse


class OrgSpendingConfigResponse(BaseModel):
    """Response from GET/PATCH /admin/orgs/{org_id}/spending."""

    org_id: str
    daily_limit_usdc: int | None = None
    monthly_limit_usdc: int | None = None
    hard_limit_usdc: int | None = None
    updated_at: str = ""

    model_config = {"extra": "allow"}
