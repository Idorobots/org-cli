"""Flow command wiring."""

import typer

from org.commands.flow import board as flow_board


def register(app: typer.Typer) -> None:
    """Register flow commands on the root CLI app."""
    flow_app = typer.Typer(
        help="Flow-focused task workflows in Org-mode archives.",
        no_args_is_help=True,
    )
    flow_board.register(flow_app)
    app.add_typer(flow_app, name="flow")
