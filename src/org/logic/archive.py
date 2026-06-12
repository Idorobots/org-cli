"""Shared helpers for archive destination resolution and subtree moves."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from org_parser.document import Heading

from org.commands.tasks.common import load_document, resolve_parent_heading, save_document


if TYPE_CHECKING:
    from org_parser.document import Document


_DEFAULT_ARCHIVE_BASE = "%s_archive::"
logger = logging.getLogger("org")


@dataclass(frozen=True)
class ArchiveLocation:
    """Resolved archive destination location for one heading."""

    raw_spec: str
    file_path: str
    parent_title: str | None


@dataclass(frozen=True)
class ArchiveTarget:
    """Resolved archive destination node target."""

    location: ArchiveLocation
    document: Document
    parent_heading: Heading | None


@dataclass(frozen=True)
class ArchiveMoveResult:
    """Result payload for one archived heading subtree move."""

    heading: Heading
    target: ArchiveTarget
    source_document: Document
    destination_document: Document


def archive_result_documents_to_save(result: ArchiveMoveResult) -> tuple[Document, ...]:
    """Return unique documents that must be persisted for one archive move."""
    if result.source_document is result.destination_document:
        return (result.source_document,)
    return (result.source_document, result.destination_document)


def _normalize_location_part(value: str, option_name: str) -> str:
    """Return non-empty normalized location part or raise CLI error."""
    normalized = value.strip()
    if not normalized:
        raise typer.BadParameter(f"{option_name} cannot be empty")
    return normalized


def _archive_property_value(heading: Heading) -> str | None:
    """Return ARCHIVE property value from heading, when present."""
    archive_value = heading.properties.get("ARCHIVE")
    if archive_value is None:
        return None
    normalized = str(archive_value).strip()
    return normalized or None


def _archive_keyword_value(document: Document) -> str | None:
    """Return ARCHIVE keyword value from document, when present."""
    last_value: str | None = None
    for keyword in document.keywords:
        if keyword.key.upper() != "ARCHIVE":
            continue
        normalized = str(keyword.value).strip()
        if normalized:
            last_value = normalized
    return last_value


def _raw_archive_spec(heading: Heading) -> str:
    """Resolve raw archive spec by property, keyword, then default."""
    property_value = _archive_property_value(heading)
    if property_value is not None:
        return property_value

    keyword_value = _archive_keyword_value(heading.document)
    if keyword_value is not None:
        return keyword_value
    return _DEFAULT_ARCHIVE_BASE


def _split_archive_spec(spec: str) -> tuple[str, str | None]:
    """Split archive spec into path pattern and optional parent heading title."""
    if "::" not in spec:
        raise typer.BadParameter(
            "Invalid archive location: expected FILE::[HEADING] format",
        )

    path_part, _, parent_part = spec.partition("::")
    normalized_path = _normalize_location_part(path_part, "Archive location path")
    normalized_parent = parent_part.strip()
    if not normalized_parent:
        return normalized_path, None
    return normalized_path, normalized_parent


def _interpolate_archive_path(path_pattern: str, source_filename: str | None) -> str:
    """Interpolate %s placeholders and resolve relative archive paths."""
    if "%s" not in path_pattern:
        path_value = path_pattern
    else:
        if source_filename is None or not source_filename.strip():
            raise typer.BadParameter("Cannot resolve archive location without source filename")
        path_value = path_pattern.replace("%s", source_filename)

    destination_path = Path(path_value).expanduser()
    if destination_path.is_absolute():
        return str(destination_path)
    if source_filename is None or not source_filename.strip():
        return str(destination_path)

    source_path = Path(source_filename).expanduser()
    source_parent = source_path.parent
    return str((source_parent / destination_path).resolve(strict=False))


def resolve_archive_location(heading: Heading) -> ArchiveLocation:
    """Resolve effective archive location for one heading."""
    raw_spec = _raw_archive_spec(heading)
    file_pattern, parent_title = _split_archive_spec(raw_spec)
    file_path = _interpolate_archive_path(file_pattern, heading.document.filename)
    return ArchiveLocation(raw_spec=raw_spec, file_path=file_path, parent_title=parent_title)


def _paths_refer_to_same_file(source_path: str, destination_path: str) -> bool:
    """Return whether two path strings point to the same file."""
    try:
        source_resolved = Path(source_path).expanduser().resolve(strict=False)
        destination_resolved = Path(destination_path).expanduser().resolve(strict=False)
    except OSError:
        source_resolved = Path(source_path).expanduser().absolute()
        destination_resolved = Path(destination_path).expanduser().absolute()
    return source_resolved == destination_resolved


def _resolve_destination_document(
    source_document: Document,
    destination_path: str,
    destination_cache: dict[str, Document],
) -> Document:
    """Resolve archive destination document from path with cache support."""
    source_filename = source_document.filename
    if source_filename and _paths_refer_to_same_file(source_filename, destination_path):
        return source_document

    try:
        cache_key = str(Path(destination_path).expanduser().resolve(strict=False))
    except OSError:
        cache_key = str(Path(destination_path).expanduser().absolute())

    cached = destination_cache.get(cache_key)
    if cached is not None:
        return cached

    destination_document = load_document(destination_path)
    destination_cache[cache_key] = destination_document
    return destination_document


def _iter_descendants(heading: Heading) -> list[Heading]:
    """Return heading descendants as a flat list."""
    descendants: list[Heading] = []
    for child in heading.children:
        descendants.append(child)
        descendants.extend(_iter_descendants(child))
    return descendants


def _archive_time_now_text() -> str:
    """Return localized archival timestamp text without seconds."""
    return datetime.now().astimezone().strftime("%Y-%m-%d %a %H:%M")


def _string_or_empty(value: object | None) -> str:
    """Return stripped string value with empty-string fallback."""
    if value is None:
        return ""
    return str(value).strip()


def _archive_metadata_properties(heading: Heading) -> dict[str, str]:
    """Build ARCHIVE_* metadata properties from current heading state."""
    source_filename = heading.document.filename
    return {
        "ARCHIVE_TIME": _archive_time_now_text(),
        "ARCHIVE_FILE": _string_or_empty(source_filename),
        "ARCHIVE_CATEGORY": _string_or_empty(heading.category),
        "ARCHIVE_TODO": _string_or_empty(heading.todo),
    }


def _apply_archive_metadata_properties(heading: Heading) -> None:
    """Set ARCHIVE_* metadata properties on heading."""
    for key, value in _archive_metadata_properties(heading).items():
        heading.properties[key] = value


def _is_descendant(candidate: Heading, ancestor: Heading) -> bool:
    """Return whether candidate node is within ancestor subtree."""
    parent = candidate.parent
    while isinstance(parent, Heading):
        if parent is ancestor:
            return True
        parent = parent.parent
    return False


def _validate_archive_parent_target(heading: Heading, parent_heading: Heading | None) -> None:
    """Validate archive parent target does not create loops."""
    if parent_heading is None:
        return
    if parent_heading is heading:
        raise typer.BadParameter("Archive parent cannot point to the task being archived")
    if _is_descendant(parent_heading, heading):
        raise typer.BadParameter("Archive parent cannot point to a descendant of archived task")


def resolve_archive_target(
    heading: Heading,
    destination_cache: dict[str, Document],
) -> ArchiveTarget:
    """Resolve archive destination document and optional parent heading."""
    location = resolve_archive_location(heading)
    destination_document = _resolve_destination_document(
        heading.document,
        location.file_path,
        destination_cache,
    )
    parent_heading: Heading | None = None
    if location.parent_title is not None:
        parent_heading = resolve_parent_heading(destination_document, location.parent_title)
        _validate_archive_parent_target(heading, parent_heading)
    return ArchiveTarget(
        location=location,
        document=destination_document,
        parent_heading=parent_heading,
    )


def move_heading_to_archive_target(heading: Heading, target: ArchiveTarget) -> None:
    """Move one heading subtree into archive target document/parent."""
    parent = heading.parent
    if parent is None:
        raise typer.BadParameter("Unable to archive heading without a parent node")

    parent.children.remove(heading)
    if target.parent_heading is None:
        target.document.children.append(heading)
    else:
        target.parent_heading.children.append(heading)

    heading.document = target.document
    for descendant in _iter_descendants(heading):
        descendant.document = target.document


def archive_heading_subtree(
    heading: Heading,
    destination_cache: dict[str, Document],
) -> ArchiveMoveResult:
    """Resolve archive target and move one heading subtree into it."""
    source_document = heading.document
    _apply_archive_metadata_properties(heading)
    target = resolve_archive_target(heading, destination_cache)
    move_heading_to_archive_target(heading, target)

    return ArchiveMoveResult(
        heading=heading,
        target=target,
        source_document=source_document,
        destination_document=target.document,
    )


def archive_heading_subtree_and_save(
    heading: Heading,
    destination_cache: dict[str, Document],
) -> ArchiveMoveResult:
    """Archive one heading subtree and persist all affected documents once."""
    archive_result = archive_heading_subtree(heading, destination_cache)
    for document in archive_result_documents_to_save(archive_result):
        logger.info("Saving archived file: %s", document.filename)
        save_document(document)
    return archive_result
