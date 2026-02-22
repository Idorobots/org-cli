"""Logging configuration for the org CLI."""

from __future__ import annotations

import logging
import sys


LOGGER_NAME = "org"


def configure_logging(verbose: bool) -> None:
    """Configure logging output based on verbosity.

    Args:
        verbose: Whether to enable INFO logging to stdout
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.propagate = False

    if verbose:
        logger.setLevel(logging.INFO)
        if not any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.INFO)
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)
    else:
        logger.setLevel(logging.WARNING)
        logger.handlers.clear()
