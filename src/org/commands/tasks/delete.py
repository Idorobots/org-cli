"""Tasks delete command."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

import typer

from org import config as config_module
from org.cli_common import resolve_input_paths
from org.commands.tasks.common import (
    resolve_single_heading,
    save_document,
    validate_exactly_one_selector,
)


if TYPE_CHECKING:
    from org_parser.document import Heading


@dataclass
class DeleteArgs:
    """Arguments for the tasks delete command."""

    files: list[str] | None
    config: str
    title: str | None
    id_value: str | None


def _remove_heading(heading: Heading) -> None:
    """Remove heading and its full subtree from parent children."""
    parent = heading.parent
    if parent is None:
        raise typer.BadParameter("Unable to delete heading without a parent node")
    parent.children.remove(heading)


def run_tasks_delete(args: DeleteArgs) -> None:
    """Run the tasks delete command."""
    title, id_value = validate_exactly_one_selector(args.title, "--title", args.id_value, "--id")
    filenames = resolve_input_paths(args.files)

    heading = resolve_single_heading(filenames, title, id_value)
    _remove_heading(heading)
    save_document(heading.document)


def register(app: typer.Typer) -> None:
    """Register the tasks delete command."""

    @app.command("delete")
    def tasks_delete(
        files: list[str] | None = typer.Argument(  # noqa: B008
            None,
            metavar="FILE",
            help="Org-mode archive files or directories to search",
        ),
        config: str = typer.Option(
            ".org-cli.json",
            "--config",
            metavar="FILE",
            help="Config file name to load from current directory",
        ),
        title: str | None = typer.Option(
            None,
            "--title",
            metavar="TEXT",
            help="Heading title text of the task to remove",
        ),
        id_value: str | None = typer.Option(
            None,
            "--id",
            metavar="TEXT",
            help="ID of the task to remove",
        ),
    ) -> None:
        """Delete one task heading and its subtree from a selected org document."""
        args = DeleteArgs(
            files=files,
            config=config,
            title=title,
            id_value=id_value,
        )
        config_module.apply_config_defaults(args)
        config_module.log_applied_config_defaults(args, sys.argv[1:], "tasks delete")
        config_module.log_command_arguments(args, "tasks delete")
        run_tasks_delete(args)
