"""Helpers for converting USDC between atomic and decimal units."""

from __future__ import annotations

_USDC_DECIMALS = 6


def format_usdc(atomic: int) -> str:
    """Convert atomic USDC (6 decimals) to a human-readable decimal string."""
    return f"{atomic / 10**_USDC_DECIMALS:.{_USDC_DECIMALS}f}"


def parse_usdc(dollars: str | float) -> int:
    """Convert a decimal USDC amount to atomic units."""
    return int(round(float(dollars) * 10**_USDC_DECIMALS))
