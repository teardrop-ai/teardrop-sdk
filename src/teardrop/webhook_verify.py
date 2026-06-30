"""Webhook signature helpers for event trigger callbacks."""

from __future__ import annotations

import hashlib
import hmac
import time


def _build_signed_payload(payload: bytes, timestamp: int) -> bytes:
    return f"{timestamp}.".encode("utf-8") + payload


def sign_webhook(payload: bytes, secret: str, *, timestamp: int | None = None) -> str:
    """Build a signature header in the format ``t=<unix>,v1=<hex>``."""
    ts = int(time.time()) if timestamp is None else int(timestamp)
    digest = hmac.new(
        secret.encode("utf-8"),
        _build_signed_payload(payload, ts),
        hashlib.sha256,
    ).hexdigest()
    return f"t={ts},v1={digest}"


def _parse_signature_header(signature_header: str) -> tuple[int, str] | None:
    pieces: dict[str, str] = {}
    for part in signature_header.split(","):
        key, sep, value = part.strip().partition("=")
        if sep:
            pieces[key] = value

    timestamp = pieces.get("t")
    signature = pieces.get("v1")
    if not timestamp or not signature:
        return None

    try:
        parsed_ts = int(timestamp)
    except ValueError:
        return None

    return parsed_ts, signature


def verify_webhook(
    payload: bytes,
    signature_header: str,
    secret: str,
    *,
    tolerance_seconds: int = 300,
) -> bool:
    """Validate webhook payload bytes against a ``t=...,v1=...`` signature header."""
    if tolerance_seconds < 0:
        raise ValueError("tolerance_seconds must be >= 0")

    parsed = _parse_signature_header(signature_header)
    if parsed is None:
        return False

    timestamp, received_sig = parsed
    now_ts = int(time.time())
    if abs(now_ts - timestamp) > tolerance_seconds:
        return False

    expected_header = sign_webhook(payload, secret, timestamp=timestamp)
    expected_sig = expected_header.partition("v1=")[2]
    return hmac.compare_digest(expected_sig, received_sig)
