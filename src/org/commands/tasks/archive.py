"""Tasks archive command."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass

import typer
from org_parser.document import Document, Heading

from org import config as config_module
from org.cli_common import resolve_input_paths
from org.commands.archive import archive_heading_subtree, archive_result_documents_to_save
from org.commands.tasks.common import (
    resolve_headings_by_query,
    resolve_task_selector_query,
    save_document,
)


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


def run_tasks_archive(args: ArchiveArgs) -> None:
    """Run the tasks archive command."""
    filenames = resolve_input_paths(args.files)
    selector_query = resolve_task_selector_query(args.query_title, args.query_id, args.query)
    selected_headings = resolve_headings_by_query(filenames, selector_query)
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


def register(app: typer.Typer) -> None:
    """Register the tasks archive command."""

    @app.command("archive")
    def tasks_archive(
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
        args = ArchiveArgs(
            files=files,
            config=config,
            query_title=query_title,
            query_id=query_id,
            query=query,
        )
        config_module.apply_config_defaults(args)
        config_module.log_applied_config_defaults(args, sys.argv[1:], "tasks archive")
        config_module.log_command_arguments(args, "tasks archive")
        run_tasks_archive(args)
