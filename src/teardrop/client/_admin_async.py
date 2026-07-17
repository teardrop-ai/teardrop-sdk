"""Async admin-only client for Teardrop API /admin/* endpoints."""

from __future__ import annotations

from teardrop.client._core import _AsyncClientBase
from teardrop.client.admin import _AdminMixin


class AsyncAdminTeardropClient(
    _AdminMixin,
    _AsyncClientBase,
):
    """Async client for Teardrop admin-only endpoints.

    Requires an admin-privileged token. Does **not** inherit the standard
    ``AsyncTeardropClient`` surface — admin methods live exclusively here.
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
        timeout: float = 120.0,
        discovery_timeout: float = 10.0,
    ):
        super().__init__(
            base_url,
            email=email,
            secret=secret,
            client_id=client_id,
            client_secret=client_secret,
            token=token,
            timeout=timeout,
            discovery_timeout=discovery_timeout,
        )
