"""CLI interface for org - Org-mode archive file analysis."""

from __future__ import annotations

import sys

import typer

import org.config.app
import org.logging
from org.commands import agenda, stats
from org.commands import board as board_command
from org.commands.tasks import command as tasks_command
from org.logic.filtering import DEFAULT_VERBOSE, resolve_verbose


app = typer.Typer(
    help="Analyze Emacs Org-mode archive files for task statistics.",
    no_args_is_help=True,
)


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
    org.logging.configure_logging(resolve_verbose(verbose))


agenda.register(app)
board_command.register(app)
stats.register(app)
tasks_command.register(app)


def main() -> None:
    """Run the CLI entry point."""
    loaded_config = org.config.app.load_cli_config(sys.argv)
    defaults = loaded_config.defaults
    if defaults is not None:
        DEFAULT_VERBOSE["value"] = bool(defaults.pop("verbose", False))
    org.config.app.CONFIG_APPEND_DEFAULTS.clear()
    org.config.app.CONFIG_APPEND_DEFAULTS.update(loaded_config.append_defaults)
    org.config.app.CONFIG_INLINE_DEFAULTS.clear()
    org.config.app.CONFIG_INLINE_DEFAULTS.update(loaded_config.inline_defaults)
    org.config.app.CONFIG_DEFAULTS.clear()
    if defaults is not None:
        org.config.app.CONFIG_DEFAULTS.update(defaults)
    org.config.app.CONFIG_CUSTOM_FILTERS.clear()
    org.config.app.CONFIG_CUSTOM_FILTERS.update(loaded_config.custom_filters)
    org.config.app.CONFIG_CUSTOM_ORDER_BY.clear()
    org.config.app.CONFIG_CUSTOM_ORDER_BY.update(loaded_config.custom_order_by)
    org.config.app.CONFIG_CUSTOM_WITH.clear()
    org.config.app.CONFIG_CUSTOM_WITH.update(loaded_config.custom_with)
    org.config.app.CONFIG_CAPTURE_TEMPLATES.clear()
    org.config.app.CONFIG_CAPTURE_TEMPLATES.update(loaded_config.capture_templates)
    org.config.app.CONFIG_BOARD_VIEWS.clear()
    org.config.app.CONFIG_BOARD_VIEWS.update(loaded_config.board_views)
    org.config.app.CONFIG_AGENDA_VIEWS.clear()
    org.config.app.CONFIG_AGENDA_VIEWS.update(loaded_config.agenda_views)

    command = typer.main.get_command(app)
    default_map = org.config.app.build_default_map(defaults) if defaults else None
    command.main(
        args=sys.argv[1:],
        prog_name="org",
        standalone_mode=True,
        default_map=default_map,
    )


if __name__ == "__main__":
    main()
