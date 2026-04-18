"""Tasks delete command."""

from __future__ import annotations

import sys
from dataclasses import dataclass

import org_parser
import typer
from org_parser.document import Document, Heading

from org import config as config_module
from org.cli_common import resolve_input_paths


@dataclass
class DeleteArgs:
    """Arguments for the tasks delete command."""

    files: list[str] | None
    config: str
    title: str | None
    id_value: str | None


def _normalize_selector(value: str | None, option_name: str) -> str | None:
    """Normalize optional selector value and reject blank strings."""
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise typer.BadParameter(f"{option_name} cannot be empty")
    return normalized


def _validate_identifiers(args: DeleteArgs) -> tuple[str | None, str | None]:
    """Validate task identifiers and return normalized values."""
    normalized_title = _normalize_selector(args.title, "--title")
    normalized_id = _normalize_selector(args.id_value, "--id")
    if normalized_title is None and normalized_id is None:
        raise typer.BadParameter("Provide exactly one task identifier: --title or --id")
    if normalized_title is not None and normalized_id is not None:
        raise typer.BadParameter("Provide exactly one task identifier: --title or --id")
    return normalized_title, normalized_id


def _load_document(path: str) -> Document:
    """Load org document from file for mutation."""
    try:
        return org_parser.load(path)
    except FileNotFoundError as err:
        raise typer.BadParameter(f"File '{path}' not found") from err
    except PermissionError as err:
        raise typer.BadParameter(f"Permission denied for '{path}'") from err
    except ValueError as err:
        raise typer.BadParameter(f"Unable to parse '{path}': {err}") from err


def _save_document(document: Document) -> None:
    """Persist updated org document back to disk."""
    try:
        org_parser.dump(document)
    except PermissionError as err:
        filename = document.filename if document.filename else "<unknown>"
        raise typer.BadParameter(f"Permission denied for '{filename}'") from err


def _title_matches(document: Document, title: str | None) -> list[Heading]:
    """Return headings matching title selector in one document."""
    if title is None:
        return []
    return [node for node in list(document) if node.title_text.strip() == title]


def _id_matches(document: Document, id_value: str | None) -> list[Heading]:
    """Return heading matching ID selector in one document."""
    if id_value is None:
        return []
    heading = document.heading_by_id(id_value)
    if heading is None:
        return []
    return [heading]


def _resolve_matches(document: Document, title: str | None, id_value: str | None) -> list[Heading]:
    """Resolve unique matches for title and ID selectors in one document."""
    unique_matches: dict[int, Heading] = {}
    for heading in [*_title_matches(document, title), *_id_matches(document, id_value)]:
        unique_matches[id(heading)] = heading
    return list(unique_matches.values())


def _remove_heading(heading: Heading) -> None:
    """Remove heading and its full subtree from parent children."""
    parent = heading.parent
    if parent is None:
        raise typer.BadParameter("Unable to delete heading without a parent node")
    parent.children.remove(heading)


def run_tasks_delete(args: DeleteArgs) -> None:
    """Run the tasks delete command."""
    title, id_value = _validate_identifiers(args)
    filenames = resolve_input_paths(args.files)

    matches: list[Heading] = []
    for filename in filenames:
        document = _load_document(filename)
        for heading in _resolve_matches(document, title, id_value):
            matches.append(heading)

    if not matches:
        raise typer.BadParameter("No task matches the provided selector")
    if len(matches) > 1:
        raise typer.BadParameter("Task selector is ambiguous, multiple tasks match")

    heading = matches[0]
    _remove_heading(heading)
    _save_document(heading.document)


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
