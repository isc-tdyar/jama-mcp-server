"""JAMA MCP Server Error Handling Utilities

Custom exception classes for JAMA API operations with standardized error messages.
"""

from typing import Optional, Dict, Any


class JamaError(Exception):
    """Base exception for all JAMA-related errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """Initialize JAMA error.

        Args:
            message: Human-readable error message
            details: Optional additional error details
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class ValidationError(JamaError):
    """Raised when request data fails validation.

    Examples:
    - Missing required fields
    - Invalid field types
    - Custom field validation failures
    """

    pass


class PermissionError(JamaError):
    """Raised when user lacks permission for an operation.

    Corresponds to HTTP 403 Forbidden responses.
    """

    pass


class AuthenticationError(JamaError):
    """Raised when authentication fails or token is invalid.

    Corresponds to HTTP 401 Unauthorized responses.
    """

    pass


class NotFoundError(JamaError):
    """Raised when requested resource doesn't exist.

    Corresponds to HTTP 404 Not Found responses.
    """

    pass


class ConflictError(JamaError):
    """Raised when operation conflicts with current resource state.

    Examples:
    - Concurrent modification (version conflict)
    - Duplicate relationship creation
    - Item is locked
    - Referential integrity violation

    Corresponds to HTTP 409 Conflict responses.
    """

    pass


class RateLimitError(JamaError):
    """Raised when API rate limit is exceeded.

    Corresponds to HTTP 429 Too Many Requests responses.
    Note: Should rarely occur due to client-side rate limiting.
    """

    pass


class ServerError(JamaError):
    """Raised when JAMA server returns an error.

    Corresponds to HTTP 5xx responses (500, 502, 503, 504).
    """

    pass


def handle_http_error(status_code: int, response_text: str) -> JamaError:
    """Convert HTTP error response to appropriate exception.

    Args:
        status_code: HTTP status code
        response_text: Response body text

    Returns:
        Appropriate JamaError subclass instance
    """
    error_map = {
        400: ValidationError,
        401: AuthenticationError,
        403: PermissionError,
        404: NotFoundError,
        409: ConflictError,
        429: RateLimitError,
    }

    if status_code in error_map:
        error_class = error_map[status_code]
        return error_class(
            f"HTTP {status_code}: {response_text}",
            details={"status_code": status_code, "response": response_text}
        )

    if 500 <= status_code < 600:
        return ServerError(
            f"HTTP {status_code}: Server error - {response_text}",
            details={"status_code": status_code, "response": response_text}
        )

    return JamaError(
        f"HTTP {status_code}: Unexpected error - {response_text}",
        details={"status_code": status_code, "response": response_text}
    )
