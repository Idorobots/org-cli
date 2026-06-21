"""CLI interface for org - Org-mode archive file analysis."""

from __future__ import annotations

import sys

import typer

import org.config.app
import org.logging
from org.commands import agenda, stats
from org.commands import board as board_command
from org.commands.tasks import command as tasks_command


def build_app(config: org.config.app.AppConfig) -> typer.Typer:
    """Build the Typer application after config is loaded."""
    app = typer.Typer(
        help="Analyze Emacs Org-mode archive files for task statistics.",
        no_args_is_help=True,
    )

    @app.callback()
    def main_callback(
        ctx: typer.Context,
        verbose: bool | None = typer.Option(
            None,
            "--verbose",
            "-v",
            help="Enable verbose logging output",
        ),
    ) -> None:
        """Global CLI options."""
        ctx.obj = config
        if verbose is None and not config.verbose:
            return
        org.logging.configure_logging(config.verbose if verbose is None else verbose)

    agenda.register(app)
    board_command.register(app)
    stats.register(app)
    tasks_command.register(app)
    return app


def main() -> None:
    """Run the CLI entry point."""
    app = build_app(org.config.app.load_cli_config(sys.argv))
    command = typer.main.get_command(app)
    command.main(
        args=sys.argv[1:],
        prog_name="org",
        standalone_mode=True,
    )


if __name__ == "__main__":
    main()
