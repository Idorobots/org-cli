"""Tasks edit command."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass

import typer

from org import config as config_module
from org.cli_common import resolve_input_paths
from org.commands.editor import edit_heading_subtree_in_external_editor
from org.commands.tasks.common import (
    resolve_headings_by_query,
    resolve_task_selector_query,
    save_document,
)


logger = logging.getLogger("org")


@dataclass
class EditArgs:
    """Arguments for the tasks edit command."""

    files: list[str] | None
    config: str
    query_title: str | None
    query_id: str | None
    query: str | None


def run_tasks_edit(args: EditArgs) -> None:
    """Run the tasks edit command."""
    filenames = resolve_input_paths(args.files)
    selector_query = resolve_task_selector_query(args.query_title, args.query_id, args.query)
    selected_headings = resolve_headings_by_query(filenames, selector_query)

    if len(selected_headings) > 1:
        raise typer.BadParameter("tasks edit requires a selector that matches exactly one task")

    heading = selected_headings[0]
    document = heading.document
    logger.info(
        "Editing task: file=%s title=%s id=%s tags=%s",
        document.filename,
        heading.title_text,
        heading.id,
        list(heading.heading_tags),
    )

    edit_result = edit_heading_subtree_in_external_editor(heading)
    if not edit_result.changed:
        logger.info("Task edit produced no content change; skipping save")
        typer.echo("No changes.")
        return

    logger.info("Saving edited file: %s", document.filename)
    save_document(document)
    typer.echo("Edited 1 task.")


def register(app: typer.Typer) -> None:
    """Register the tasks edit command."""

    @app.command("edit")
    def tasks_edit(
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
            help="Heading title text of the task to edit",
        ),
        query_id: str | None = typer.Option(
            None,
            "--query-id",
            metavar="TEXT",
            help="ID of the task to edit",
        ),
        query: str | None = typer.Option(
            None,
            "--query",
            metavar="QUERY",
            help="Generic query language selector expression",
        ),
    ) -> None:
        """Edit one task subtree in an external editor."""
        args = EditArgs(
            files=files,
            config=config,
            query_title=query_title,
            query_id=query_id,
            query=query,
        )
        config_module.apply_config_defaults(args)
        config_module.log_applied_config_defaults(args, sys.argv[1:], "tasks edit")
        config_module.log_command_arguments(args, "tasks edit")
        run_tasks_edit(args)
