"""Shared helpers for task mutation commands."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import org_parser
import typer
from org_parser.document import Heading
from org_parser.text import CompletionCounter
from org_parser.time import Timestamp

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


def parse_comment_flag(value: str) -> bool:
    """Parse --comment value as strict true/false."""
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise typer.BadParameter("--comment must be either 'true' or 'false'")


def normalize_optional_value(value: str) -> str | None:
    """Return stripped value or None for blank input."""
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def parse_counter(value: str) -> CompletionCounter | None:
    """Parse --counter value into completion counter or None."""
    normalized = normalize_optional_value(value)
    if normalized is None:
        return None
    if normalized.startswith("[") and normalized.endswith("]"):
        normalized = normalized[1:-1].strip()
    if not normalized:
        return None
    return CompletionCounter(normalized)


def parse_timestamp(value: str, option_name: str | None = None) -> Timestamp | None:
    """Parse timestamp option value into Timestamp or None."""
    normalized = normalize_optional_value(value)
    if normalized is None:
        return None
    try:
        return Timestamp.from_source(normalized)
    except (TypeError, ValueError) as err:
        if option_name is None:
            raise typer.BadParameter(f"Value {value!r} is not a valid Org timestamp") from err
        raise typer.BadParameter(
            f"{option_name} value {value!r} is not a valid Org timestamp",
        ) from err


def iter_descendants(heading: Heading) -> list[Heading]:
    """Return heading descendants as a flat list."""
    descendants: list[Heading] = []
    for child in heading.children:
        descendants.append(child)
        descendants.extend(iter_descendants(child))
    return descendants


def apply_subtree_level(heading: Heading, new_level: int) -> None:
    """Apply heading level and shift descendants by the same delta."""
    level_delta = new_level - heading.level
    if level_delta == 0:
        return

    heading.level = new_level
    for descendant in iter_descendants(heading):
        descendant.level += level_delta


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


def resolve_parent_heading(document: Document, parent_value: str) -> Heading:
    """Resolve one parent heading by id first, then title."""
    selector = normalize_selector(parent_value, "--parent")
    if selector is None:
        raise typer.BadParameter("--parent cannot be empty")

    id_matches_list = id_matches(document, selector)
    if id_matches_list:
        return id_matches_list[0]

    title_matches_list = title_matches(document, selector)
    if len(title_matches_list) > 1:
        raise typer.BadParameter(
            f"--parent is ambiguous, multiple headings with title '{selector}'",
        )
    if len(title_matches_list) == 1:
        return title_matches_list[0]

    raise typer.BadParameter(f"--parent '{selector}' was not found")


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
