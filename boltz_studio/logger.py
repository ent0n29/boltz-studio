"""Logging configuration for Boltz Studio."""

import logging
import sys
from typing import Optional


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure and return the application logger.

    Args:
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("boltz_studio")

    if logger.handlers:
        return logger

    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Optional child logger name (e.g., 'routes', 'services')

    Returns:
        Logger instance
    """
    base = "boltz_studio"
    if name:
        return logging.getLogger(f"{base}.{name}")
    return logging.getLogger(base)


# Initialize the main logger
logger = setup_logging()
