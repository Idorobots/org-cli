"""Shared helpers for task mutation commands."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import org_parser
import typer
from org_parser.document import Heading

from org.query_language import (
    EvalContext,
    QueryParseError,
    QueryRuntimeError,
    Stream,
    compile_query_text,
)


if TYPE_CHECKING:
    from org_parser.document import Document


logger = logging.getLogger("org")


def normalize_selector(value: str | None, option_name: str) -> str | None:
    """Normalize optional selector value and reject blank strings."""
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise typer.BadParameter(f"{option_name} cannot be empty")
    return normalized


def resolve_task_selector_query(
    query_title: str | None,
    query_id: str | None,
    query: str | None,
) -> str:
    """Resolve task selector into one query-language expression."""
    normalized_title = normalize_selector(query_title, "--query-title")
    normalized_id = normalize_selector(query_id, "--query-id")
    normalized_query = normalize_selector(query, "--query")

    selectors = [
        normalized_title is not None,
        normalized_id is not None,
        normalized_query is not None,
    ]
    if sum(selectors) != 1:
        raise typer.BadParameter(
            "Provide exactly one task selector: --query-title, --query-id, or --query",
        )

    if normalized_query is not None:
        return f".[] | select({normalized_query})"
    if normalized_title is not None:
        return f'.[] | select(str(.title_text) == "{normalized_title}")'
    return f".[] | select(str(.id) == {json.dumps(normalized_id)})"


def load_document(path: str) -> Document:
    """Load org document from file for mutation."""
    try:
        return org_parser.load(path)
    except FileNotFoundError as err:
        raise typer.BadParameter(f"File '{path}' not found") from err
    except PermissionError as err:
        raise typer.BadParameter(f"Permission denied for '{path}'") from err
    except ValueError as err:
        raise typer.BadParameter(f"Unable to parse '{path}': {err}") from err


def save_document(document: Document) -> None:
    """Persist updated org document back to disk."""
    try:
        org_parser.dump(document)
    except PermissionError as err:
        filename = document.filename or "<unknown>"
        raise typer.BadParameter(f"Permission denied for '{filename}'") from err


def title_matches(document: Document, title: str | None) -> list[Heading]:
    """Return headings matching title selector in one document."""
    if title is None:
        return []
    return [node for node in list(document) if node.title_text.strip() == title]


def id_matches(document: Document, id_value: str | None) -> list[Heading]:
    """Return heading matching ID selector in one document."""
    if id_value is None:
        return []
    heading = document.heading_by_id(id_value)
    if heading is None:
        return []
    return [heading]


def parse_tags_csv(value: str) -> list[str]:
    """Parse comma-separated tag option into tag list."""
    normalized = value.strip()
    if not normalized:
        return []
    tags = [tag.strip() for tag in normalized.split(",")]
    if not tags or any(not tag for tag in tags):
        raise typer.BadParameter("--tags must be a comma-separated list of non-empty tags")
    return tags


def parse_properties_json(value: str) -> dict[str, str]:
    """Parse properties JSON option into a string dictionary."""
    normalized = value.strip()
    if not normalized:
        return {}

    try:
        loaded = json.loads(normalized)
    except json.JSONDecodeError as err:
        raise typer.BadParameter("--properties must be a valid JSON object") from err

    if not isinstance(loaded, dict):
        raise typer.BadParameter("--properties must be a JSON object")

    parsed: dict[str, str] = {}
    for key, property_value in loaded.items():
        if not isinstance(key, str) or not key.strip():
            raise typer.BadParameter("--properties keys must be non-empty strings")
        if not isinstance(property_value, str):
            raise typer.BadParameter("--properties values must be strings")
        parsed[key] = property_value
    return parsed


def resolve_headings_by_query(
    filenames: list[str],
    selector_query: str,
) -> list[Heading]:
    """Resolve matching headings across files from selector query."""
    try:
        compiled_query = compile_query_text(selector_query)
    except QueryParseError as err:
        raise typer.BadParameter(f"Invalid task selector query: {err}") from err

    logger.info("Task selector query: %s", selector_query)
    matches_by_identity: dict[int, Heading] = {}
    for filename in filenames:
        document = load_document(filename)
        logger.info("Running task selector query against file: %s", filename)
        try:
            results = compiled_query(Stream([document]), EvalContext({}))
        except QueryRuntimeError as err:
            raise typer.BadParameter(f"Task selector query failed: {err}") from err

        for value in results:
            if not isinstance(value, Heading):
                raise typer.BadParameter(
                    "Task selector query must return task headings",
                )
            matches_by_identity[id(value)] = value

    matches = list(matches_by_identity.values())
    if not matches:
        raise typer.BadParameter("No task matches the provided selector")
    return matches
