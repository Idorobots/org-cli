"""Tasks command wiring."""

import typer

from org.commands.tasks import add as tasks_add
from org.commands.tasks import list as tasks_list
from org.commands.tasks import remove as tasks_remove
from org.commands.tasks import update as tasks_update


def register(app: typer.Typer) -> None:
    """Register tasks commands on the root CLI app."""
    tasks_app = typer.Typer(
        help="Search and update tasks in Org-mode archives.",
        no_args_is_help=True,
    )
    tasks_add.register(tasks_app)
    tasks_remove.register(tasks_app)
    tasks_update.register(tasks_app)
    tasks_list.register(tasks_app)
    app.add_typer(tasks_app, name="tasks")
