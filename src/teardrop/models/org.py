"""Organization credential models."""

from __future__ import annotations

from pydantic import BaseModel


class OrgCredentialsEntry(BaseModel):
    """A single M2M credential entry (secret is never returned)."""

    client_id: str
    created_at: str = ""


class RegenerateCredentialsResponse(BaseModel):
    """Response from POST /org/credentials/regenerate."""

    client_id: str
    client_secret: str
    created_at: str = ""
