"""Output format abstraction and format-specific renderers."""

from __future__ import annotations

import logging
import shlex
import subprocess
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum

import orgparse
from orgparse.date import OrgDate
from orgparse.node import OrgRootNode
from rich.console import Console
from rich.syntax import Syntax

from org.tui import print_output


logger = logging.getLogger("org")

DEFAULT_OUTPUT_THEME = "github-dark"


_RENDERABLE_OUTPUT_FORMATS: dict[str, str] = {
    "bibtex": "bibtex",
    "commonmark": "markdown",
    "commonmark_x": "markdown",
    "docbook": "xml",
    "docbook4": "xml",
    "docbook5": "xml",
    "gfm": "markdown",
    "haddock": "markdown",
    "html": "html",
    "html4": "html",
    "html5": "html",
    "jats": "xml",
    "jats_archiving": "xml",
    "jats_articleauthoring": "xml",
    "jats_publishing": "xml",
    "json": "json",
    "latex": "latex",
    "man": "man",
    "markdown": "markdown",
    "markdown_github": "markdown",
    "markdown_mmd": "markdown",
    "markdown_phpextra": "markdown",
    "markdown_strict": "markdown",
    "mediawiki": "mediawiki",
    "ms": "ms",
    "org": "org",
    "rst": "rst",
    "tei": "xml",
    "textile": "textile",
    "typst": "typst",
    "xwiki": "mediawiki",
    "zimwiki": "mediawiki",
}


class OutputFormat(StrEnum):
    """Supported output formats."""

    ORG = "org"
    JSON = "json"


@dataclass(frozen=True)
class OutputOperation:
    """One prepared output operation."""

    kind: str
    text: str | None = None
    data: bytes | None = None
    renderable: object | None = None
    markup: bool = False
    color_enabled: bool = False
    end: str = "\n"


@dataclass(frozen=True)
class PreparedOutput:
    """Prepared output operations ready for console rendering."""

    operations: tuple[OutputOperation, ...]


class OutputFormatError(RuntimeError):
    """Raised when output formatting fails."""


def _write_plain_output(console: Console, text: str) -> None:
    """Write plain output directly to console stream."""
    console.file.write(f"{text}\n")
    console.file.flush()


def _write_binary_output(console: Console, data: bytes) -> None:
    """Write binary output directly to console stream."""
    buffer = getattr(console.file, "buffer", None)
    if buffer is not None:
        buffer.write(data)
        buffer.flush()
        return
    raise OutputFormatError("binary output is not supported by the active console stream")


def print_prepared_output(console: Console, prepared_output: PreparedOutput) -> None:
    """Print already prepared output operations."""
    for operation in prepared_output.operations:
        if operation.kind == "plain_write":
            if operation.text is not None:
                _write_plain_output(console, operation.text)
            continue
        if operation.kind == "binary_write":
            if operation.data is not None:
                _write_binary_output(console, operation.data)
            continue
        if operation.kind == "print_output":
            if operation.text is not None:
                print_output(
                    console,
                    operation.text,
                    operation.color_enabled,
                    end=operation.end,
                )
            continue
        if operation.renderable is not None:
            console.print(operation.renderable)
            continue
        console.print(operation.text if operation.text is not None else "", markup=operation.markup)


def _resolve_syntax_language(output_format: str) -> str | None:
    """Resolve output format to a syntax highlighter language alias."""
    normalized_output = output_format.strip().lower()
    return _RENDERABLE_OUTPUT_FORMATS.get(normalized_output)


def _normalize_syntax_theme(out_theme: str) -> str:
    """Return a valid theme name for syntax rendering."""
    normalized_theme = out_theme.strip()
    if normalized_theme:
        return normalized_theme
    return DEFAULT_OUTPUT_THEME


def _prepare_output(
    value: str | bytes,
    color_enabled: bool,
    output_format: str,
    out_theme: str,
) -> PreparedOutput:
    """Prepare output with syntax highlighting when available."""
    if isinstance(value, bytes):
        try:
            text = value.decode("utf-8")
        except UnicodeDecodeError:
            return PreparedOutput(operations=(OutputOperation(kind="binary_write", data=value),))
    else:
        text = value

    if color_enabled:
        language = _resolve_syntax_language(output_format)
        if language is not None:
            return PreparedOutput(
                operations=(
                    OutputOperation(
                        kind="console_print",
                        renderable=Syntax(
                            text,
                            language,
                            theme=_normalize_syntax_theme(out_theme),
                            line_numbers=False,
                            word_wrap=True,
                        ),
                    ),
                )
            )
    return PreparedOutput(operations=(OutputOperation(kind="plain_write", text=text),))


def _to_org_input_text(value: object) -> str:
    """Convert arbitrary query value into org text for markdown conversion."""
    if isinstance(value, orgparse.node.OrgNode | OrgRootNode):
        return str(value)
    if isinstance(value, OrgDate) and not bool(value):
        return "none"
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _build_org_document(values: list[object]) -> str:
    """Build one org document from all output values."""
    parts = [_to_org_input_text(value) for value in values]
    non_empty_parts = [part for part in parts if part]
    return "".join(non_empty_parts)


def _parse_pandoc_args(pandoc_args: str | None) -> list[str]:
    """Parse optional pandoc args string into argument list."""
    if pandoc_args is None or not pandoc_args.strip():
        return []
    try:
        return shlex.split(pandoc_args)
    except ValueError as exc:
        raise OutputFormatError(str(exc)) from exc


def _org_to_pandoc_format(org_text: str, output_format: str, pandoc_args: list[str]) -> bytes:
    """Convert org text into the requested output format using one pandoc invocation."""
    try:
        command = ["pandoc", "-f", "org", "-t", output_format, *pandoc_args]
        result = subprocess.run(
            command,
            input=org_text.encode("utf-8"),
            capture_output=True,
            check=False,
        )
    except (OSError, ValueError) as exc:
        raise OutputFormatError(str(exc)) from exc

    stderr_text = result.stderr.decode("utf-8", errors="replace").strip()
    if result.returncode != 0:
        message = (
            stderr_text if stderr_text else f"pandoc failed with exit code {result.returncode}"
        )
        raise OutputFormatError(message)

    if stderr_text:
        for line in stderr_text.splitlines():
            logger.info("pandoc warning: %s", line)

    return result.stdout


_NODE_EXPORTED_FIELDS = (
    "body",
    "clock",
    "closed",
    "datelist",
    "deadline",
    "heading",
    "level",
    "linenumber",
    "priority",
    "properties",
    "rangelist",
    "repeated_tasks",
    "scheduled",
    "shallow_tags",
    "tags",
    "todo",
)
_ROOT_EXPORTED_FIELDS = (
    "body",
    "datelist",
    "env",
    "heading",
    "level",
    "linenumber",
    "properties",
    "rangelist",
    "shallow_tags",
    "tags",
)
_ENV_EXPORTED_FIELDS = (
    "all_todo_keys",
    "done_keys",
    "filename",
    "todo_keys",
)
_DATE_EXPORTED_FIELDS = (
    "active",
    "end",
    "duration",
    "start",
)


def _is_primitive_json_type(value: object) -> bool:
    """Return whether the value maps directly to a JSON primitive."""
    return value is None or isinstance(value, bool | int | float | str)


def _exported_org_fields(value: object) -> tuple[str, ...]:
    """Return explicit exported field names for each org object type."""
    if isinstance(value, OrgRootNode):
        return _ROOT_EXPORTED_FIELDS
    if isinstance(value, orgparse.node.OrgNode):
        return _NODE_EXPORTED_FIELDS
    if isinstance(value, orgparse.node.OrgEnv):
        return _ENV_EXPORTED_FIELDS
    return _DATE_EXPORTED_FIELDS


def _org_object_to_json_dict(value: object, seen: set[int]) -> dict[str, object]:
    """Serialize org object public attributes into a JSON object."""
    data: dict[str, object] = {"type": type(value).__name__}
    for field_name in _exported_org_fields(value):
        if not hasattr(value, field_name):
            continue
        field_value = getattr(value, field_name)
        data[field_name] = _to_json_compatible(field_value, seen)
    return data


def _iterable_to_json_list(value: object, seen: set[int]) -> list[object]:
    """Convert iterable values into JSON arrays."""
    if isinstance(value, Iterable):
        return [_to_json_compatible(item, seen) for item in value]
    return [str(value)]


def _to_json_compatible(value: object, seen: set[int] | None = None) -> object:
    """Convert arbitrary values to JSON-serializable structures."""
    if _is_primitive_json_type(value):
        return value

    if seen is None:
        seen = set()

    obj_id = id(value)
    if obj_id in seen:
        return None

    result: object
    if isinstance(value, datetime | date | time):
        result = value.isoformat()
    elif isinstance(value, bytes):
        result = value.decode("utf-8", errors="replace")
    elif isinstance(value, OrgDate | orgparse.node.OrgNode | OrgRootNode | orgparse.node.OrgEnv):
        seen.add(obj_id)
        result = _org_object_to_json_dict(value, seen)
    elif isinstance(value, Mapping):
        seen.add(obj_id)
        result = {str(key): _to_json_compatible(item, seen) for key, item in value.items()}
    elif isinstance(value, Iterable):
        seen.add(obj_id)
        result = _iterable_to_json_list(value, seen)
    else:
        result = str(value)
    return result


def _json_output_payload(values: list[object]) -> object:
    """Convert formatter values to final JSON payload shape."""
    converted = [_to_json_compatible(value) for value in values]
    if len(converted) == 1:
        return converted[0]
    return converted
