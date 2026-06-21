"""Stats command wiring."""

from __future__ import annotations

import typer

import org.config.app
import org.logging
from org.commands.stats import all as stats_all
from org.commands.stats import groups, tags
from org.commands.stats import summary as stats_summary


stats_app = typer.Typer(
    help="Analyze Org-mode archive files for task statistics.",
    no_args_is_help=True,
)


@stats_app.callback()
def stats_callback(
    ctx: typer.Context,
    verbose: bool | None = typer.Option(
        None,
        "--verbose",
        "-v",
        help="Enable verbose logging output",
    ),
) -> None:
    """Global stats CLI options."""
    app_config = org.config.app.require_app_config(ctx)
    if verbose is None and not app_config.verbose:
        return
    org.logging.configure_logging(app_config.verbose if verbose is None else verbose)


def register(app: typer.Typer) -> None:
    """Register stats commands on the root CLI app."""
    stats_all.register(stats_app)
    groups.register(stats_app)
    stats_summary.register(stats_app)
    tags.register(stats_app)
    app.add_typer(stats_app, name="stats")
