"""Tasks archive command."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import typer
from org_parser.document import Document, Heading

import org.config.app
import org.logging
from org.commands.tasks.common import (
    resolve_task_selector_query,
    save_document,
    selected_heading_results,
)
from org.logic.archive import archive_heading_subtree, archive_result_documents_to_save
from org.pipeline.load import load_documents, resolve_input_paths, resolve_loaded_state_context
from org.query.engine.errors import QueryParseError, QueryRuntimeError
from org.query.runner import run_query


logger = logging.getLogger("org")


@dataclass
class ArchiveArgs:
    """Arguments for the tasks archive command."""

    files: list[str] | None
    config: str
    query_title: str | None
    query_id: str | None
    query: str | None


def _selected_archive_roots(headings: list[Heading]) -> list[Heading]:
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


def run_tasks_archive(args: ArchiveArgs, config: org.config.app.AppConfig) -> None:
    """Run the tasks archive command."""
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
    archive_roots = _selected_archive_roots(selected_headings)
    destination_cache: dict[str, Document] = {}

    documents_to_save: dict[int, Document] = {}
    for heading in archive_roots:
        archive_result = archive_heading_subtree(heading, destination_cache)
        logger.info(
            "Archiving task: file=%s title=%s id=%s destination=%s parent=%s",
            archive_result.source_document.filename,
            archive_result.heading.title_text,
            archive_result.heading.id,
            archive_result.destination_document.filename,
            (
                archive_result.target.parent_heading.title_text
                if archive_result.target.parent_heading is not None
                else ""
            ),
        )
        for document in archive_result_documents_to_save(archive_result):
            documents_to_save[id(document)] = document

    for document in documents_to_save.values():
        logger.info("Saving archived file: %s", document.filename)
        save_document(document)

    typer.echo(f"Archived {len(archive_roots)} tasks.")


def register(app: typer.Typer, config: org.config.app.AppConfig) -> None:
    """Register the tasks archive command."""
    del config

    @app.command("archive")
    def tasks_archive(  # noqa: PLR0913
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
            help="Heading title text of the task to archive",
        ),
        query_id: str | None = typer.Option(
            None,
            "--query-id",
            metavar="TEXT",
            help="ID of the task to archive",
        ),
        query: str | None = typer.Option(
            None,
            "--query",
            metavar="QUERY",
            help="Generic query language selector expression",
        ),
    ) -> None:
        """Archive selected task heading and subtree."""
        app_config = org.config.app.require_app_config(ctx)
        args = ArchiveArgs(
            files=files,
            config=config,
            query_title=query_title,
            query_id=query_id,
            query=query,
        )
        org.logging.log_command_config(app_config, "tasks archive")
        org.logging.log_command_arguments(args, "tasks archive")
        run_tasks_archive(args, app_config)
