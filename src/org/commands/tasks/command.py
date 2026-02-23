"""Tasks command wiring."""

import typer

from org.commands.tasks import list as tasks_list


def register(app: typer.Typer) -> None:
    """Register tasks commands on the root CLI app."""
    tasks_app = typer.Typer(
        help="Search and update tasks in Org-mode archives.",
        no_args_is_help=True,
    )
    tasks_list.register(tasks_app)
    app.add_typer(tasks_app, name="tasks")
