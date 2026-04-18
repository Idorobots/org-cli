"""Tasks delete command."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

import typer

from org import config as config_module
from org.cli_common import resolve_input_paths
from org.commands.tasks.common import (
    resolve_single_heading_by_query,
    resolve_task_selector_query,
    save_document,
)


if TYPE_CHECKING:
    from org_parser.document import Heading


logger = logging.getLogger("org")


@dataclass
class DeleteArgs:
    """Arguments for the tasks delete command."""

    files: list[str] | None
    config: str
    query_title: str | None
    query_id: str | None
    query: str | None


def _remove_heading(heading: Heading) -> None:
    """Remove heading and its full subtree from parent children."""
    parent = heading.parent
    if parent is None:
        raise typer.BadParameter("Unable to delete heading without a parent node")
    parent.children.remove(heading)


def run_tasks_delete(args: DeleteArgs) -> None:
    """Run the tasks delete command."""
    filenames = resolve_input_paths(args.files)
    selector_query = resolve_task_selector_query(args.query_title, args.query_id, args.query)

    heading = resolve_single_heading_by_query(filenames, selector_query)
    logger.info(
        "Deleting task from file=%s title=%s id=%s tags=%s",
        heading.document.filename,
        heading.title_text,
        heading.id,
        list(heading.heading_tags),
    )
    _remove_heading(heading)
    logger.info("Saving file after delete: %s", heading.document.filename)
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
        query_title: str | None = typer.Option(
            None,
            "--query-title",
            metavar="TEXT",
            help="Heading title text of the task to remove",
        ),
        query_id: str | None = typer.Option(
            None,
            "--query-id",
            metavar="TEXT",
            help="ID of the task to remove",
        ),
        query: str | None = typer.Option(
            None,
            "--query",
            metavar="QUERY",
            help="Generic query language selector expression",
        ),
    ) -> None:
        """Delete one task heading and its subtree from a selected org document."""
        args = DeleteArgs(
            files=files,
            config=config,
            query_title=query_title,
            query_id=query_id,
            query=query,
        )
        config_module.apply_config_defaults(args)
        config_module.log_applied_config_defaults(args, sys.argv[1:], "tasks delete")
        config_module.log_command_arguments(args, "tasks delete")
        run_tasks_delete(args)
