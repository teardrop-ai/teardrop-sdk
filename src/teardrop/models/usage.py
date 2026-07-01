"""Usage summary models."""

from __future__ import annotations

from pydantic import BaseModel


class UsageSummary(BaseModel):
    total_runs: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_tool_calls: int = 0
    total_duration_ms: int = 0
