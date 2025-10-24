"""Logging configuration for festival planner."""

import logging
import sys
import structlog


def configure_logging(level: str = "INFO") -> None:
    """Configure structured logging for the application.

    Args:
        level: Log level as string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Convert string level to logging level
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
    )

    # Disable info-level logging for hishel and httpx (too verbose)
    # These libraries log too much detail about HTTP requests/responses
    for verbose_logger in [
        "hishel",
        "hishel.controller",
        "hishel.cache",
        "httpx",
        "httpcore",
        "httpcore.connection",
        "httpcore.http11",
    ]:
        logging.getLogger(verbose_logger).setLevel(logging.WARNING)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.rich_traceback,
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a logger instance for a module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)
