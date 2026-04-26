"""Shared test fixtures and helpers for the Teardrop SDK test suite."""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from teardrop.client import AsyncTeardropClient


def _make_jwt(exp: float | None = None, extra: dict | None = None) -> str:
    """Build a minimal unsigned JWT string.

    The signature segment is the literal string "sig" so tests can use
    ``token="tok.en.sig"`` directly as a static token without triggering
    real JWT validation.  When exp is set the token manager's _read_exp()
    will decode it successfully.
    """
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=")
    payload_dict: dict = extra or {}
    if exp is not None:
        payload_dict["exp"] = exp
    payload = base64.urlsafe_b64encode(json.dumps(payload_dict).encode()).rstrip(b"=")
    return f"{header.decode()}.{payload.decode()}.sig"


def _json_response(
    body: dict | list, status: int = 200, headers: dict | None = None
) -> httpx.Response:
    """Build a fake httpx.Response with a JSON body."""
    return httpx.Response(
        status_code=status,
        content=json.dumps(body).encode(),
        headers={"content-type": "application/json", **(headers or {})},
        request=httpx.Request("GET", "http://test"),
    )


@pytest.fixture
def client():
    """A bare AsyncTeardropClient using a static token (no network calls)."""
    return AsyncTeardropClient("http://test", token="tok.en.sig")


@pytest.fixture
def mock_http(client):
    """Inject an AsyncMock HTTP client and patch get_token.

    Yields the mock so tests can configure return values and assert calls.
    """
    mock = AsyncMock()
    mock.is_closed = False
    client._http = mock
    with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
        yield mock
