"""Tasks remove command."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass

import typer
from org_parser.document import Document, Heading
from rich.console import Console
from rich.prompt import Confirm

from org import config as config_module
from org.cli_common import resolve_input_paths
from org.color import should_use_color
from org.commands.tasks.common import (
    resolve_headings_by_query,
    resolve_task_selector_query,
    save_document,
)


logger = logging.getLogger("org")


@dataclass
class RemoveArgs:
    """Arguments for the tasks remove command."""

    files: list[str] | None
    config: str
    query_title: str | None
    query_id: str | None
    query: str | None
    yes: bool
    color_flag: bool | None


def _remove_heading(heading: Heading) -> None:
    """Remove heading and its full subtree from parent children."""
    parent = heading.parent
    if parent is None:
        raise typer.BadParameter("Unable to delete heading without a parent node")
    parent.children.remove(heading)


def _selected_delete_roots(headings: list[Heading]) -> list[Heading]:
    """Return selected headings that are not descendants of another selected heading."""
    selected_by_id = {id(heading) for heading in headings}
    roots: list[Heading] = []
    for heading in headings:
        parent = heading.parent
        skip = False
        while isinstance(parent, Heading):
            if id(parent) in selected_by_id:
                skip = True
                break
            parent = parent.parent
        if not skip:
            roots.append(heading)
    return roots


def run_tasks_remove(args: RemoveArgs) -> None:
    """Run the tasks remove command."""
    filenames = resolve_input_paths(args.files)
    selector_query = resolve_task_selector_query(args.query_title, args.query_id, args.query)

    selected_headings = resolve_headings_by_query(filenames, selector_query)
    selected_count = len(selected_headings)
    logger.info("Selected %s tasks for delete", selected_count)

    if not args.yes:
        color_enabled = should_use_color(args.color_flag)
        console = Console(no_color=not color_enabled, force_terminal=color_enabled)
        confirmed = Confirm.ask(
            f"Delete {selected_count} tasks?",
            console=console,
            default=False,
            show_default=True,
            show_choices=True,
        )
        if not confirmed:
            logger.info("Delete operation cancelled by user")
            typer.echo("Cancelled")
            return

    delete_roots = _selected_delete_roots(selected_headings)
    affected_documents: dict[int, Document] = {}
    for heading in delete_roots:
        logger.info(
            "Deleting task from file=%s title=%s id=%s tags=%s",
            heading.document.filename,
            heading.title_text,
            heading.id,
            list(heading.heading_tags),
        )
        _remove_heading(heading)
        document = heading.document
        affected_documents[id(document)] = document

    for document in affected_documents.values():
        logger.info("Saving file after delete: %s", document.filename)
        document.sync_heading_id_index()
        save_document(document)

    typer.echo(f"Deleted {selected_count} tasks.")


def register(app: typer.Typer) -> None:
    """Register the tasks remove command."""

    @app.command("remove")
    def tasks_remove(  # noqa: PLR0913
        files: list[str] | None = typer.Argument(  # noqa: B008
            None,
            metavar="FILE",
            help="Org-mode archive files or directories to search",
        ),
        config: str = typer.Option(
            ".org-cli.yaml",
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
        yes: bool = typer.Option(
            False,
            "--yes",
            help="Automatically confirm without prompting",
        ),
        color_flag: bool | None = typer.Option(
            None,
            "--color/--no-color",
            help="Force colored output",
        ),
    ) -> None:
        """Delete one task heading and its subtree from a selected org document."""
        args = RemoveArgs(
            files=files,
            config=config,
            query_title=query_title,
            query_id=query_id,
            query=query,
            yes=yes,
            color_flag=color_flag,
        )
        config_module.apply_config_defaults(args)
        config_module.log_applied_config_defaults(args, sys.argv[1:], "tasks remove")
        config_module.log_command_arguments(args, "tasks remove")
        run_tasks_remove(args)
