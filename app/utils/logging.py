"""
Structured logging configuration.
"""

import logging
import sys
from typing import Any, Dict
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

import structlog
from structlog.types import Processor

from app.config import settings

# Query parameters that must never appear in logs
_SENSITIVE_PARAMS = {"token", "secret", "key", "password", "passwd", "api_key"}


def setup_logging() -> None:
    """
    Configure structured logging for the application.

    Sets up structlog with JSON output for production
    and colored console output for development.
    """
    # Determine if we're in development mode
    is_development = settings.app_env == "development" or settings.debug

    # Common processors
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if is_development:
        # Development: colored console output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # Production: JSON output
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.getLevelName(settings.log_level.upper()),
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)

    logger = structlog.get_logger(__name__)
    logger.info(
        "Logging configured",
        level=settings.log_level,
        environment=settings.app_env,
    )


def strip_sensitive_params(url: str) -> str:
    """
    Remove sensitive query parameters (e.g. ``token``) from a URL string.

    Parameters whose names (case-insensitive) are in ``_SENSITIVE_PARAMS``
    are replaced with ``[REDACTED]``.
    """
    parsed = urlparse(url)
    if not parsed.query:
        return url
    qs = parse_qs(parsed.query, keep_blank_values=True)
    sanitised = {
        k: ["[REDACTED]"] if k.lower() in _SENSITIVE_PARAMS else v
        for k, v in qs.items()
    }
    # urlencode with doseq=True to handle multi-valued params
    clean_query = urlencode(sanitised, doseq=True)
    return urlunparse(parsed._replace(query=clean_query))


def get_request_context(request) -> Dict[str, Any]:
    """
    Extract context from a FastAPI request for logging.

    Args:
        request: The FastAPI request object

    Returns:
        Dictionary with request context
    """
    return {
        "method": request.method,
        "url": strip_sensitive_params(str(request.url)),
        "client_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }
