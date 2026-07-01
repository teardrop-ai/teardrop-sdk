"""Authentication-related response models."""

from __future__ import annotations

from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str | None = None


class JwtPayloadBase(BaseModel):
    """Decoded JWT payload returned by GET /auth/me."""

    sub: str | None = None
    user_id: str | None = None
    org_id: str = ""
    role: str = ""
    auth_method: str = ""
    email: str | None = None
    iss: str | None = None
    exp: int | None = None
    iat: int | None = None
    address: str | None = None
    chain_id: int | None = None

    @property
    def effective_sub(self) -> str | None:
        """Return sub or user_id - whichever is present."""
        return self.sub or self.user_id

    model_config = {"extra": "allow"}


class MeResponse(JwtPayloadBase):
    """Response from GET /auth/me with org metadata."""

    org_name: str = ""
