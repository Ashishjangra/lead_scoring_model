import logging
import os
import time
import uuid
from collections.abc import Callable
from typing import Any

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.constants import (
    ENV_DEBUG,
    ENV_DEV,
    LOG_FILE_PATH,
    LOG_FORMAT,
    LOG_LEVEL_DEBUG,
    LOG_LEVEL_INFO,
)


def setup_logger() -> logging.Logger:
    """
    Set up logger with CloudWatch and local file handlers based on environment.

    Returns:
        Configured logger instance
    """
    # Get environment
    env = os.getenv("ENV", ENV_DEV).lower()

    # Create logger
    logger = logging.getLogger("lead-scoring")
    logger.setLevel(LOG_LEVEL_DEBUG if env == ENV_DEBUG else LOG_LEVEL_INFO)

    # Clear existing handlers
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT)

    # Add console handler for all environments
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # For now, use console logging only - ECS captures stdout/stderr
    # This eliminates CloudWatch setup issues during debugging
    logger.info(f"Logger configured for {env} environment - using console output")

    # Add file handler for debug environment
    if env == ENV_DEBUG:
        try:
            # Ensure log directory exists
            os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)

            file_handler = logging.FileHandler(LOG_FILE_PATH)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        except Exception as e:
            logger.warning(f"Failed to setup file logging: {e}")

    return logger


# Initialize logger
logger = setup_logger()

# Configure structlog to use the configured logger
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

# Get structlog logger
struct_logger = structlog.get_logger()


class LoggingMiddleware(BaseHTTPMiddleware):
    """Structured logging middleware for request/response tracking"""

    async def dispatch(
        self, request: Request, call_next: Callable[..., Any]
    ) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Start timing
        start_time = time.time()

        # Log request
        struct_logger.info(
            "Request started",
            request_id=request_id,
            method=request.method,
            url=str(request.url),
            user_agent=request.headers.get("user-agent"),
            client_ip=request.client.host if request.client else None,
        )

        try:
            # Process request
            response: Response = await call_next(request)

            # Calculate duration
            duration = time.time() - start_time

            # Log response
            struct_logger.info(
                "Request completed",
                request_id=request_id,
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2),
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            duration = time.time() - start_time

            struct_logger.error(
                "Request failed",
                request_id=request_id,
                error=str(e),
                duration_ms=round(duration * 1000, 2),
            )
            raise
