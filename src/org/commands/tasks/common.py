"""Shared helpers for task mutation commands."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import org_parser
import typer


if TYPE_CHECKING:
    from org_parser.document import Document, Heading


def normalize_selector(value: str | None, option_name: str) -> str | None:
    """Normalize optional selector value and reject blank strings."""
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise typer.BadParameter(f"{option_name} cannot be empty")
    return normalized


def validate_exactly_one_selector(
    first_value: str | None,
    first_option: str,
    second_value: str | None,
    second_option: str,
) -> tuple[str | None, str | None]:
    """Validate selector pair where exactly one option must be provided."""
    normalized_first = normalize_selector(first_value, first_option)
    normalized_second = normalize_selector(second_value, second_option)
    if normalized_first is None and normalized_second is None:
        raise typer.BadParameter(
            f"Provide exactly one task identifier: {first_option} or {second_option}",
        )
    if normalized_first is not None and normalized_second is not None:
        raise typer.BadParameter(
            f"Provide exactly one task identifier: {first_option} or {second_option}",
        )
    return normalized_first, normalized_second


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


def resolve_single_heading(
    filenames: list[str],
    title: str | None,
    id_value: str | None,
) -> Heading:
    """Resolve one heading across files by title or ID."""
    matches: list[Heading] = []
    for filename in filenames:
        document = load_document(filename)
        selector_matches = id_matches(document, id_value)
        if id_value is None:
            selector_matches = title_matches(document, title)
        matches.extend(selector_matches)

    if not matches:
        raise typer.BadParameter("No task matches the provided selector")
    if len(matches) > 1:
        raise typer.BadParameter("Task selector is ambiguous, multiple tasks match")
    return matches[0]
