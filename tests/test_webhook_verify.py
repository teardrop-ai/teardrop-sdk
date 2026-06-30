"""Tests for webhook signature helpers."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from teardrop.webhook_verify import sign_webhook, verify_webhook


def test_sign_and_verify_round_trip() -> None:
    payload = b'{"event":"payment"}'
    secret = "whsec_test"
    timestamp = 1_720_000_000

    header = sign_webhook(payload, secret, timestamp=timestamp)

    with patch("teardrop.webhook_verify.time.time", return_value=timestamp):
        assert verify_webhook(payload, header, secret)


def test_verify_rejects_tampered_payload() -> None:
    payload = b'{"event":"payment"}'
    secret = "whsec_test"
    timestamp = 1_720_000_000

    header = sign_webhook(payload, secret, timestamp=timestamp)

    with patch("teardrop.webhook_verify.time.time", return_value=timestamp):
        assert not verify_webhook(b'{"event":"refund"}', header, secret)


def test_verify_rejects_expired_signature() -> None:
    payload = b'{"event":"payment"}'
    secret = "whsec_test"
    timestamp = 1_720_000_000

    header = sign_webhook(payload, secret, timestamp=timestamp)

    with patch("teardrop.webhook_verify.time.time", return_value=timestamp + 301):
        assert not verify_webhook(payload, header, secret, tolerance_seconds=300)


def test_verify_rejects_malformed_header() -> None:
    payload = b'{"event":"payment"}'
    secret = "whsec_test"

    assert not verify_webhook(payload, "invalid", secret)


def test_verify_rejects_negative_tolerance() -> None:
    payload = b'{"event":"payment"}'
    secret = "whsec_test"

    with pytest.raises(ValueError):
        verify_webhook(payload, "t=1,v1=abcd", secret, tolerance_seconds=-1)
