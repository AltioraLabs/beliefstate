"""Shared utilities for all integrations."""

import logging
import time
from typing import Any, Callable, Optional
from functools import wraps
import uuid

logger = logging.getLogger(__name__)


class IntegrationLogger:
    """Structured logging for integrations."""

    def __init__(self, name: str, integration_type: str):
        self.logger = logging.getLogger(name)
        self.integration_type = integration_type

    def _log(self, level: str, operation: str, **metadata: Any) -> None:
        """Log with structured metadata."""
        msg = f"[{self.integration_type}] {operation}"
        getattr(self.logger, level)(
            msg, extra={"integration": self.integration_type, **metadata}
        )

    def debug(self, operation: str, **metadata: Any) -> None:
        self._log("debug", operation, **metadata)

    def info(self, operation: str, **metadata: Any) -> None:
        self._log("info", operation, **metadata)

    def warning(self, operation: str, **metadata: Any) -> None:
        self._log("warning", operation, **metadata)

    def error(self, operation: str, **metadata: Any) -> None:
        self._log("error", operation, **metadata)


class RequestIDGenerator:
    """Generate unique request IDs for tracing."""

    @staticmethod
    def generate() -> str:
        """Generate a unique request ID."""
        return str(uuid.uuid4())


def track_request(integration_type: str = "integration") -> Callable:
    """Decorator to track request latency and errors.

    Usage:
        @track_request("fastapi")
        async def handle_request():
            ...
    """
    log = IntegrationLogger(__name__, integration_type)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            request_id = RequestIDGenerator.generate()
            start_time = time.time()

            try:
                log.debug(
                    "Request started", request_id=request_id, function=func.__name__
                )
                result = await func(*args, **kwargs)
                latency = time.time() - start_time
                log.info(
                    "Request completed",
                    request_id=request_id,
                    function=func.__name__,
                    latency_seconds=round(latency, 3),
                )
                return result
            except Exception as e:
                latency = time.time() - start_time
                log.error(
                    "Request failed",
                    request_id=request_id,
                    function=func.__name__,
                    error=str(e),
                    latency_seconds=round(latency, 3),
                )
                raise

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            request_id = RequestIDGenerator.generate()
            start_time = time.time()

            try:
                log.debug(
                    "Request started", request_id=request_id, function=func.__name__
                )
                result = func(*args, **kwargs)
                latency = time.time() - start_time
                log.info(
                    "Request completed",
                    request_id=request_id,
                    function=func.__name__,
                    latency_seconds=round(latency, 3),
                )
                return result
            except Exception as e:
                latency = time.time() - start_time
                log.error(
                    "Request failed",
                    request_id=request_id,
                    function=func.__name__,
                    error=str(e),
                    latency_seconds=round(latency, 3),
                )
                raise

        # Return async wrapper if the function is async, otherwise sync wrapper
        if hasattr(func, "__await__") or "async" in str(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def validate_session_id(session_id: Optional[str]) -> str:
    """Validate and normalize a session ID.

    Args:
        session_id: Session ID to validate

    Returns:
        Valid session ID

    Raises:
        ValueError: If session ID is invalid
    """
    if not session_id or not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("Session ID must be a non-empty string")
    return session_id.strip()


def format_error_response(error: Exception, request_id: str) -> dict[str, Any]:
    """Format an exception as a standard error response.

    Args:
        error: Exception to format
        request_id: Request ID for correlation

    Returns:
        Error response dictionary
    """
    return {
        "error": str(error),
        "error_type": type(error).__name__,
        "request_id": request_id,
    }
