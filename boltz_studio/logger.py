"""Logging configuration for Boltz Studio."""

import logging
import sys
from typing import Optional


# Global handler to be shared
_handler: logging.Handler | None = None


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure and return the application logger.

    Args:
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    global _handler

    logger = logging.getLogger("boltz_studio")

    if logger.handlers:
        return logger

    logger.setLevel(level)

    _handler = logging.StreamHandler(sys.stdout)
    _handler.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    _handler.setFormatter(formatter)

    logger.addHandler(_handler)
    # Don't propagate to root logger (avoid duplicate logs)
    logger.propagate = False

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Optional child logger name (e.g., 'routes', 'services')

    Returns:
        Logger instance
    """
    # Ensure main logger is setup first
    setup_logging()

    base = "boltz_studio"
    if name:
        child_logger = logging.getLogger(f"{base}.{name}")
        # Ensure child loggers inherit the level
        child_logger.setLevel(logging.INFO)
        return child_logger
    return logging.getLogger(base)


# Initialize the main logger
logger = setup_logging()
