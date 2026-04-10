"""Token lifecycle management for Teardrop SDK."""

from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any

import httpx

from teardrop.exceptions import AuthenticationError
from teardrop.models import TokenResponse

logger = logging.getLogger(__name__)

# Buffer before expiry to trigger a refresh (seconds).
_REFRESH_BUFFER = 30


class TokenManager:
    """Manages JWT token acquisition and auto-refresh.

    Supports three auth modes:
    - ``email`` + ``secret``
    - ``client_id`` + ``client_secret``
    - Pre-authenticated ``token`` (no refresh)
    """

    def __init__(
        self,
        base_url: str,
        *,
        email: str | None = None,
        secret: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        token: str | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._email = email
        self._secret = secret
        self._client_id = client_id
        self._client_secret = client_secret
        self._token = token
        self._expires_at: float = 0.0

        if token:
            self._expires_at = self._read_exp(token)

    @property
    def can_refresh(self) -> bool:
        """Whether this manager has credentials to request a new token."""
        return bool(self._email and self._secret) or bool(
            self._client_id and self._client_secret
        )

    async def get_token(self, client: httpx.AsyncClient) -> str:
        """Return a valid token, refreshing if expired or about to expire."""
        if self._token and (time.time() < self._expires_at - _REFRESH_BUFFER):
            return self._token

        if not self.can_refresh:
            if self._token:
                return self._token  # Static token, no refresh possible.
            raise AuthenticationError("No credentials configured for token refresh.")

        self._token = await self._fetch_token(client)
        self._expires_at = self._read_exp(self._token)
        return self._token

    async def _fetch_token(self, client: httpx.AsyncClient) -> str:
        """POST /token to obtain a fresh JWT."""
        body: dict[str, Any] = {}
        if self._email and self._secret:
            body = {"email": self._email, "secret": self._secret}
        elif self._client_id and self._client_secret:
            body = {"client_id": self._client_id, "client_secret": self._client_secret}

        resp = await client.post(f"{self._base_url}/token", json=body)
        if resp.status_code != 200:
            raise AuthenticationError(f"Token request failed: {resp.status_code} {resp.text}")

        data = TokenResponse.model_validate(resp.json())
        return data.access_token

    async def authenticate_siwe(
        self, client: httpx.AsyncClient, siwe_message: str, siwe_signature: str
    ) -> str:
        """Authenticate via a pre-signed SIWE message.

        Returns the JWT token and stores it for subsequent requests.
        """
        body = {"siwe_message": siwe_message, "siwe_signature": siwe_signature}
        resp = await client.post(f"{self._base_url}/token", json=body)
        if resp.status_code != 200:
            raise AuthenticationError(f"SIWE auth failed: {resp.status_code} {resp.text}")

        data = TokenResponse.model_validate(resp.json())
        self._token = data.access_token
        self._expires_at = self._read_exp(self._token)
        return self._token

    @staticmethod
    def _read_exp(token: str) -> float:
        """Decode JWT payload (without verification) to read ``exp`` claim.

        Returns 0.0 if the token cannot be parsed.
        """
        try:
            parts = token.split(".")
            if len(parts) < 2:
                return 0.0
            # Add padding for base64url decoding.
            payload_b64 = parts[1]
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            return float(payload.get("exp", 0))
        except Exception:
            return 0.0
