import logging
import os
import time
import uuid
from collections.abc import Callable
from typing import Any

import boto3  # type: ignore
import structlog
import watchtower
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.constants import (
    ENV_DEBUG,
    ENV_DEV,
    ENV_PROD,
    LOG_FILE_PATH,
    LOG_FORMAT,
    LOG_GROUP_NAME,
    LOG_LEVEL_DEBUG,
    LOG_LEVEL_INFO,
    LOG_STREAM_DEV,
    LOG_STREAM_PROD,
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

    # Add CloudWatch handler for dev and prod environments
    if env in [ENV_DEV, ENV_PROD]:
        try:
            # Determine log stream based on environment
            log_stream = LOG_STREAM_DEV if env == ENV_DEV else LOG_STREAM_PROD

            # Create boto3 client
            logs_client = boto3.client("logs")

            # Create CloudWatch handler
            cloudwatch_handler = watchtower.CloudWatchLogHandler(
                log_group_name=LOG_GROUP_NAME,
                log_stream_name=log_stream,
                boto3_client=logs_client,
                create_log_group=True,
                create_log_stream=True,
            )
            cloudwatch_handler.setFormatter(formatter)
            logger.addHandler(cloudwatch_handler)

        except Exception as e:
            # Fallback to console logging if CloudWatch setup fails
            logger.warning(f"Failed to setup CloudWatch logging: {e}")

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
