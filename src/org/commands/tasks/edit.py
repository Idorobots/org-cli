"""Tasks edit command."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import typer

import org.config.app
import org.logging
from org.commands.tasks.common import (
    resolve_task_selector_query,
    selected_heading_results,
)
from org.logic.edit import edit_heading_subtree_in_external_editor
from org.pipeline.load import load_documents, resolve_input_paths, resolve_loaded_state_context
from org.query.engine.errors import QueryParseError, QueryRuntimeError
from org.query.runner import run_query


logger = logging.getLogger("org")


@dataclass
class EditArgs:
    """Arguments for the tasks edit command."""

    files: list[str] | None
    config: str
    query_title: str | None
    query_id: str | None
    query: str | None


def run_tasks_edit(args: EditArgs, config: org.config.app.AppConfig) -> None:
    """Run the tasks edit command."""
    filenames = resolve_input_paths(args.files)
    selector_query = resolve_task_selector_query(args.query_title, args.query_id, args.query)
    documents = load_documents(filenames)
    todo_states, done_states = resolve_loaded_state_context(
        documents,
        config.todo_states,
        config.done_states,
    )

    logger.info("Task selector query: %s", selector_query)
    try:
        results = run_query(
            documents,
            [selector_query],
            {"todo_states": todo_states, "done_states": done_states},
        )
    except QueryParseError as exc:
        raise typer.BadParameter(f"Invalid task selector query: {exc}") from exc
    except QueryRuntimeError as exc:
        raise typer.BadParameter(f"Task selector query failed: {exc}") from exc

    selected_headings = selected_heading_results(results)
    if not selected_headings:
        raise typer.BadParameter("No task matches the provided selector")

    if len(selected_headings) > 1:
        raise typer.BadParameter("tasks edit requires a selector that matches exactly one task")

    heading = selected_headings[0]
    logger.info(
        "Editing task: file=%s title=%s id=%s tags=%s",
        heading.document.filename,
        heading.title_text,
        heading.id,
        list(heading.heading_tags),
    )

    edit_result = edit_heading_subtree_in_external_editor(heading)
    if not edit_result.changed:
        logger.info("Task edit produced no content change; skipping save")
        typer.echo("No changes.")
        return

    typer.echo("Edited 1 task.")


def register(app: typer.Typer, config: org.config.app.AppConfig) -> None:
    """Register the tasks edit command."""
    del config

    @app.command("edit")
    def tasks_edit(  # noqa: PLR0913
        ctx: typer.Context,
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
        app_config = org.config.app.require_app_config(ctx)
        org.logging.log_command_config(app_config, "tasks edit")
        org.logging.log_command_arguments(args, "tasks edit")
        run_tasks_edit(args, app_config)
