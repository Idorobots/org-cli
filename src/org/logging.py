"""Logging configuration and command logging helpers."""

from __future__ import annotations

import logging
import sys

import org.config.app


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


def _format_default_log_entry(option_name: str, value: object) -> str:
    """Format one option/value pair for config-default logging."""
    return f"{option_name}={value!r}"


def _format_argument_log_entry(arg_name: str, value: object) -> str:
    """Format one argument/value pair for command argument logging."""
    return f"{arg_name}={value!r}"


def _redact_inline_config_value(option_name: str, value: object) -> object:
    """Redact inline mapping/exclude values in default logs."""
    if option_name in {"--mapping", "--exclude"} and isinstance(value, (dict, list)):
        return "<Value ellided...>"
    return value


def log_applied_config_defaults(
    config: org.config.app.AppConfig,
    _args: object,
    command_name: str,
) -> None:
    """Log effective config values available to one command."""
    if not logger.isEnabledFor(logging.INFO):
        return

    entries: list[str] = []

    for dest, default_value in sorted(org.config.app.command_config_values(config).items()):
        option_name = org.config.app.DEST_TO_OPTION_NAME.get(dest)
        if option_name is None:
            continue
        entries.append(
            _format_default_log_entry(
                option_name,
                _redact_inline_config_value(option_name, default_value),
            ),
        )

    if entries:
        logger.info("Effective config (%s): %s", command_name, ", ".join(entries))


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
