"""Organization credential models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OrgCredentialsEntry(BaseModel):
    """A single M2M credential entry (secret is never returned)."""

    client_id: str
    created_at: str = ""


class OrgCredentialsResponse(BaseModel):
    """Response from GET /org/credentials."""

    credentials: list[OrgCredentialsEntry] = Field(default_factory=list)


class RegenerateCredentialsResponse(BaseModel):
    """Response from POST /org/credentials/regenerate."""

    client_id: str
    client_secret: str
    created_at: str = ""
