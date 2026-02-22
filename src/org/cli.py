#!/usr/bin/env python
"""CLI interface for org - Org-mode archive file analysis."""

from __future__ import annotations

import sys

import typer

from org import config, logging_config
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

app.add_typer(stats_app, name="stats")


def main() -> None:
    """Main CLI entry point."""
    defaults, append_defaults, inline_defaults = config.load_cli_config(sys.argv)
    if defaults is not None:
        DEFAULT_VERBOSE["value"] = bool(defaults.pop("verbose", False))
    config.CONFIG_APPEND_DEFAULTS.clear()
    config.CONFIG_APPEND_DEFAULTS.update(append_defaults)
    config.CONFIG_INLINE_DEFAULTS.clear()
    config.CONFIG_INLINE_DEFAULTS.update(inline_defaults)

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
