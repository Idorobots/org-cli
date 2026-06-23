"""Tasks command wiring."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from org.commands.tasks import add as tasks_add
from org.commands.tasks import archive as tasks_archive
from org.commands.tasks import capture as tasks_capture
from org.commands.tasks import edit as tasks_edit
from org.commands.tasks import find as tasks_find
from org.commands.tasks import list as tasks_list
from org.commands.tasks import query as tasks_query
from org.commands.tasks import remove as tasks_remove
from org.commands.tasks import update as tasks_update


if TYPE_CHECKING:
    import org.config.app


def register(app: typer.Typer, config: org.config.app.AppConfig) -> None:
    """Register tasks commands on the root CLI app."""
    tasks_app = typer.Typer(
        help="Search and update tasks in Org-mode archives.",
        no_args_is_help=True,
    )
    tasks_add.register(tasks_app, config)
    tasks_archive.register(tasks_app, config)
    tasks_capture.register(tasks_app, config)
    tasks_edit.register(tasks_app, config)
    tasks_find.register(tasks_app, config)
    tasks_list.register(tasks_app, config)
    tasks_query.register(tasks_app, config)
    tasks_remove.register(tasks_app, config)
    tasks_update.register(tasks_app, config)
    app.add_typer(tasks_app, name="tasks")
