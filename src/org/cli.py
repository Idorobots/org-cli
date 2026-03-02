#!/usr/bin/env python
"""CLI interface for org - Org-mode archive file analysis."""

from __future__ import annotations

import sys

import typer

from org import config, logging_config
from org.commands import query
from org.commands.stats import groups, summary, tags
from org.commands.stats import tasks as stats_tasks
from org.commands.tasks import command as tasks_command


app = typer.Typer(
    help="Analyze Emacs Org-mode archive files for task statistics.",
    no_args_is_help=True,
)
stats_app = typer.Typer(
    help="Analyze Org-mode archive files for task statistics.",
    no_args_is_help=True,
)


DEFAULT_VERBOSE: dict[str, bool] = {"value": False}


def _resolve_verbose(verbose: bool | None) -> bool:
    if verbose is None:
        return DEFAULT_VERBOSE["value"]
    return verbose


@app.callback()
def main_callback(
    verbose: bool | None = typer.Option(
        None,
        "--verbose",
        "-v",
        help="Enable verbose logging output",
    ),
) -> None:
    """Global CLI options."""
    if verbose is None and not DEFAULT_VERBOSE["value"]:
        return
    logging_config.configure_logging(_resolve_verbose(verbose))


@stats_app.callback()
def stats_callback(
    verbose: bool | None = typer.Option(
        None,
        "--verbose",
        "-v",
        help="Enable verbose logging output",
    ),
) -> None:
    """Global stats CLI options."""
    if verbose is None and not DEFAULT_VERBOSE["value"]:
        return
    logging_config.configure_logging(_resolve_verbose(verbose))


summary.register(stats_app)
tags.register(stats_app)
groups.register(stats_app)
stats_tasks.register(stats_app)
tasks_command.register(app)
query.register(app)

app.add_typer(stats_app, name="stats")


def main() -> None:
    """Main CLI entry point."""
    loaded_config = config.load_cli_config(sys.argv)
    defaults = loaded_config.defaults
    if defaults is not None:
        DEFAULT_VERBOSE["value"] = bool(defaults.pop("verbose", False))
    config.CONFIG_APPEND_DEFAULTS.clear()
    config.CONFIG_APPEND_DEFAULTS.update(loaded_config.append_defaults)
    config.CONFIG_INLINE_DEFAULTS.clear()
    config.CONFIG_INLINE_DEFAULTS.update(loaded_config.inline_defaults)
    config.CONFIG_DEFAULTS.clear()
    if defaults is not None:
        config.CONFIG_DEFAULTS.update(defaults)
    config.CONFIG_CUSTOM_FILTERS.clear()
    config.CONFIG_CUSTOM_FILTERS.update(loaded_config.custom_filters)
    config.CONFIG_CUSTOM_ORDER_BY.clear()
    config.CONFIG_CUSTOM_ORDER_BY.update(loaded_config.custom_order_by)
    config.CONFIG_CUSTOM_WITH.clear()
    config.CONFIG_CUSTOM_WITH.update(loaded_config.custom_with)

    command = typer.main.get_command(app)
    default_map = config.build_default_map(defaults) if defaults else None
    command.main(
        args=sys.argv[1:],
        prog_name="org",
        standalone_mode=True,
        default_map=default_map,
    )


if __name__ == "__main__":
    main()
