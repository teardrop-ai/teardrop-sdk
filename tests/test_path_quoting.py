"""Tests for safe interpolation of user-controlled URL path segments."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from teardrop.client import AsyncTeardropClient
from teardrop.client._core import _quote_path_segment


def _json_response(body: dict) -> httpx.Response:
    return httpx.Response(
        status_code=200,
        content=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://test"),
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("tool/name", "tool%2Fname"),
        ("../billing", "..%2Fbilling"),
        ("name with spaces", "name%20with%20spaces"),
        ("100%", "100%25"),
    ],
)
def test_quote_path_segment_escapes_reserved_characters(value: str, expected: str) -> None:
    assert _quote_path_segment(value) == expected


@pytest.mark.asyncio
async def test_public_route_keeps_traversal_shaped_id_in_one_segment() -> None:
    client = AsyncTeardropClient("http://test", token="tok.en.sig")
    mock_http = AsyncMock()
    mock_http.is_closed = False
    mock_http.get = AsyncMock(return_value=_json_response({"total_runs": 0}))
    client._http = mock_http

    with patch.object(client._token_manager, "get_token", return_value="tok.en.sig"):
        with pytest.warns(DeprecationWarning):
            await client.get_admin_usage_org("../billing")

    assert mock_http.get.call_args.args[0] == "http://test/admin/usage/org/..%2Fbilling"
