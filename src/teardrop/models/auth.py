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


class AuthMeResponse(MeResponse):
    """Alias matching the OpenAPI schema name for GET /auth/me."""


class SiweNonceResponse(BaseModel):
    """Response from GET /auth/siwe/nonce."""

    nonce: str

    model_config = {"extra": "allow"}


class VerifyEmailResponse(BaseModel):
    """Response from GET /auth/verify-email."""

    message: str = ""

    model_config = {"extra": "allow"}


class ResendVerificationResponse(BaseModel):
    """Response from POST /auth/resend-verification."""

    message: str = ""

    model_config = {"extra": "allow"}


class CreateInviteResponse(BaseModel):
    """Response from POST /org/invite."""

    invite_url: str
    email: str | None = None
    role: str = "member"
    expires_at: str | None = None

    model_config = {"extra": "allow"}


class CreateUserResponse(BaseModel):
    """Response from POST /admin/users."""

    id: str
    email: str
    org_id: str
    role: str
    created_at: str = ""

    model_config = {"extra": "allow"}


class CreateOrgResponse(BaseModel):
    """Response from POST /admin/orgs."""

    id: str
    name: str
    created_at: str = ""

    model_config = {"extra": "allow"}


class CreateClientCredentialsResponse(BaseModel):
    """Response from POST /admin/client-credentials."""

    client_id: str
    client_secret: str
    org_id: str
    created_at: str

    model_config = {"extra": "allow"}
