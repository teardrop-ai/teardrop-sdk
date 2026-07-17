"""Authentication and identity client methods."""

from __future__ import annotations

from teardrop.models import (
    AuthMeResponse,
    CreateInviteResponse,
    ResendVerificationResponse,
    SiweNonceResponse,
    TokenResponse,
    VerifyEmailResponse,
)


class _AuthMixin:
    async def get_siwe_nonce(self) -> SiweNonceResponse:
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/auth/siwe/nonce")
        self._raise_for_status(resp)
        return SiweNonceResponse.model_validate(resp.json())

    async def authenticate_siwe(self, message: str, signature: str) -> str:
        http = await self._get_http()
        return await self._token_manager.authenticate_siwe(http, message, signature)

    async def get_me(self) -> AuthMeResponse:
        http = await self._get_http()
        resp = await http.get(f"{self._base_url}/auth/me", headers=await self._headers())
        self._raise_for_status(resp)
        return AuthMeResponse.model_validate(resp.json())

    async def register(self, *, org_name: str, email: str, password: str) -> TokenResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/register",
            json={"org_name": org_name, "email": email, "password": password},
        )
        self._raise_for_status(resp)
        data = TokenResponse.model_validate(resp.json())
        self._token_manager._token = data.access_token
        self._token_manager._refresh_token = data.refresh_token
        self._token_manager._expires_at = self._token_manager._read_exp(data.access_token)
        return data

    async def register_invite(self, *, token: str, email: str, password: str) -> TokenResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/register/invite",
            json={"token": token, "email": email, "password": password},
        )
        self._raise_for_status(resp)
        data = TokenResponse.model_validate(resp.json())
        self._token_manager._token = data.access_token
        self._token_manager._refresh_token = data.refresh_token
        self._token_manager._expires_at = self._token_manager._read_exp(data.access_token)
        return data

    async def refresh(self, refresh_token: str) -> TokenResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        self._raise_for_status(resp)
        data = TokenResponse.model_validate(resp.json())
        self._token_manager._token = data.access_token
        self._token_manager._refresh_token = data.refresh_token
        self._token_manager._expires_at = self._token_manager._read_exp(data.access_token)
        return data

    async def logout(self, refresh_token: str) -> None:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/auth/logout",
            json={"refresh_token": refresh_token},
            headers=await self._headers(),
        )
        self._raise_for_status(resp)

    async def verify_email(self, token: str) -> VerifyEmailResponse:
        http = await self._get_http()
        resp = await http.get(
            f"{self._base_url}/auth/verify-email",
            params={"token": token},
        )
        self._raise_for_status(resp)
        return VerifyEmailResponse.model_validate(resp.json())

    async def resend_verification(self, email: str) -> ResendVerificationResponse:
        http = await self._get_http()
        resp = await http.post(
            f"{self._base_url}/auth/resend-verification",
            json={"email": email},
        )
        self._raise_for_status(resp)
        return ResendVerificationResponse.model_validate(resp.json())

    async def invite(
        self, *, email: str | None = None, role: str = "member"
    ) -> CreateInviteResponse:
        http = await self._get_http()
        body: dict[str, str] = {"role": role}
        if email:
            body["email"] = email
        resp = await http.post(
            f"{self._base_url}/org/invite",
            json=body,
            headers=await self._headers(),
        )
        self._raise_for_status(resp)
        return CreateInviteResponse.model_validate(resp.json())
