"""Logging configuration and command logging helpers."""

from __future__ import annotations

import logging
import sys


LOGGER_NAME = "org"
logger = logging.getLogger(LOGGER_NAME)


def configure_logging(verbose: bool) -> None:
    """Configure logging output based on verbosity.

    Args:
        verbose: Whether to enable INFO logging to stdout
    """
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


def _format_argument_log_entry(arg_name: str, value: object) -> str:
    """Format one argument/value pair for command argument logging."""
    return f"{arg_name}={value!r}"


def _redact_config_value(field_name: str, value: object) -> object:
    """Redact inline mapping/exclude values in config logs."""
    if field_name in {"mapping_inline", "exclude_inline"} and isinstance(value, (dict, list)):
        return "<Value ellided...>"
    return value


def log_command_config(config: object, command_name: str) -> None:
    """Log config object used to run one command."""
    if not logger.isEnabledFor(logging.INFO):
        return

    try:
        config_items = vars(config).items()
    except TypeError:
        return

    entries = [
        _format_argument_log_entry(field_name, _redact_config_value(field_name, field_value))
        for field_name, field_value in sorted(config_items, key=lambda item: item[0])
    ]

    if entries:
        logger.info("Command config (%s): %s", command_name, ", ".join(entries))


def log_command_arguments(args: object, command_name: str) -> None:
    """Log all final argument values used to run a command."""
    if not logger.isEnabledFor(logging.INFO):
        return

    try:
        arg_items = vars(args).items()
    except TypeError:
        return

    entries = [
        _format_argument_log_entry(arg_name, arg_value)
        for arg_name, arg_value in sorted(arg_items, key=lambda item: item[0])
    ]
    logger.info("Command arguments (%s): %s", command_name, ", ".join(entries))
