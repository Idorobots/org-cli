"""Stats command wiring."""

from __future__ import annotations

import typer

import org.logging
from org.cli_common import DEFAULT_VERBOSE, resolve_verbose
from org.commands.stats import all as stats_all
from org.commands.stats import groups, tags
from org.commands.stats import summary as stats_summary


stats_app = typer.Typer(
    help="Analyze Org-mode archive files for task statistics.",
    no_args_is_help=True,
)


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
    org.logging.configure_logging(resolve_verbose(verbose))


def register(app: typer.Typer) -> None:
    """Register stats commands on the root CLI app."""
    stats_all.register(stats_app)
    groups.register(stats_app)
    stats_summary.register(stats_app)
    tags.register(stats_app)
    app.add_typer(stats_app, name="stats")
