"""Teardrop SDK exception hierarchy."""

from __future__ import annotations

from typing import Any


class TeardropError(Exception):
    """Base exception for all Teardrop SDK errors."""


class AuthenticationError(TeardropError):
    """Raised on 401 Unauthorized responses."""

    def __init__(self, detail: str = "Authentication failed"):
        self.detail = detail
        super().__init__(detail)


class PaymentRequiredError(TeardropError):
    """Raised on 402 Payment Required responses.

    Attributes:
        requirements: The x402 payment requirements dict from the server.
    """

    def __init__(
        self, detail: str = "Payment required", requirements: dict[str, Any] | None = None
    ):
        self.detail = detail
        self.requirements = requirements or {}
        super().__init__(detail)


class RateLimitError(TeardropError):
    """Raised on 429 Too Many Requests responses.

    Attributes:
        retry_after: Seconds to wait before retrying (from Retry-After header).
    """

    def __init__(self, detail: str = "Rate limit exceeded", retry_after: int = 60):
        self.detail = detail
        self.retry_after = retry_after
        super().__init__(detail)


class ForbiddenError(TeardropError):
    """Raised on 403 Forbidden responses (authenticated but not authorized)."""

    def __init__(self, detail: str = "Forbidden"):
        self.detail = detail
        super().__init__(detail)


class APIError(TeardropError):
    """Catch-all for non-2xx responses not covered by specific exceptions.

    Attributes:
        status_code: HTTP status code.
        body: Response body (parsed JSON or raw text).
    """

    def __init__(self, status_code: int, body: Any = None, detail: str = ""):
        self.status_code = status_code
        self.body = body
        self.detail = detail or f"API error {status_code}"
        super().__init__(self.detail)


class NotFoundError(APIError):
    """Raised on 404 Not Found responses."""

    def __init__(self, detail: str = "Not found"):
        super().__init__(404, detail=detail)


class ConflictError(APIError):
    """Raised on 409 Conflict responses (e.g. duplicate MCP server name)."""

    def __init__(self, detail: str = "Conflict"):
        super().__init__(409, detail=detail)


class ValidationError(APIError):
    """Raised on 422 Unprocessable Entity responses (server-side validation failure)."""

    def __init__(self, detail: str = "Validation error"):
        super().__init__(422, detail=detail)


class GatewayError(APIError):
    """Raised on 502 Bad Gateway responses (e.g. MCP server unreachable)."""

    def __init__(self, detail: str = "Bad gateway"):
        super().__init__(502, detail=detail)
