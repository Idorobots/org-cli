"""Output format abstraction and format-specific renderers."""

from __future__ import annotations

import json
import logging
import shlex
import subprocess
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum
from typing import Protocol

import orgparse
from orgparse.date import OrgDate
from orgparse.node import OrgRootNode
from rich.console import Console
from rich.syntax import Syntax

from org.tui import TaskLineConfig, format_task_line, lines_to_text, print_output


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


class QueryOutputFormatter(Protocol):
    """Formatter interface for the query command."""

    include_filenames: bool

    def prepare(
        self, values: list[object], console: Console, color_enabled: bool, out_theme: str
    ) -> PreparedOutput:
        """Prepare query output values for rendering."""
        ...


class TasksListOutputFormatter(Protocol):
    """Formatter interface for the tasks list command."""

    include_filenames: bool

    def prepare(self, data: TasksListRenderInput) -> PreparedOutput:
        """Prepare tasks list output for rendering."""
        ...


@dataclass(frozen=True)
class OutputOperation:
    """One prepared output operation."""

    kind: str
    text: str | None = None
    renderable: object | None = None
    markup: bool = False
    color_enabled: bool = False
    end: str = "\n"


@dataclass(frozen=True)
class PreparedOutput:
    """Prepared output operations ready for console rendering."""

    operations: tuple[OutputOperation, ...]


@dataclass(frozen=True)
class TasksListRenderInput:
    """Render input for tasks list output formatters."""

    nodes: list[orgparse.node.OrgNode]
    console: Console
    color_enabled: bool
    done_keys: list[str]
    todo_keys: list[str]
    details: bool
    buckets: int
    out_theme: str


def _is_org_object(value: object) -> bool:
    """Return whether value is an org node or org date object."""
    return isinstance(value, orgparse.node.OrgNode | OrgRootNode | OrgDate)


def _format_org_block(value: object) -> str:
    """Build org-formatted text block for one value."""
    if isinstance(value, orgparse.node.OrgNode | OrgRootNode):
        filename = value.env.filename if value.env.filename else "unknown"
        node_text = str(value).rstrip()
        return f"# {filename}\n{node_text}" if node_text else f"# {filename}"
    if isinstance(value, OrgDate) and not bool(value):
        return "none"
    return str(value)


def _format_query_value(value: object) -> str:
    """Format one query result value for output."""
    if isinstance(value, orgparse.node.OrgNode):
        return str(value).rstrip()
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class OrgQueryOutputFormatter:
    """Org output formatter for query command."""

    include_filenames = True

    def prepare(
        self, values: list[object], console: Console, color_enabled: bool, out_theme: str
    ) -> PreparedOutput:
        del console
        del color_enabled
        if values and all(_is_org_object(value) for value in values):
            return self._prepare_org_values(values, out_theme)

        lines = [_format_query_value(value) for value in values]
        if not lines:
            return PreparedOutput(
                operations=(OutputOperation(kind="console_print", text="No results", markup=False),)
            )

        return PreparedOutput(
            operations=tuple(
                OutputOperation(kind="console_print", text=line, markup=False) for line in lines
            )
        )

    def _prepare_org_values(self, values: list[object], out_theme: str) -> PreparedOutput:
        """Prepare org values using org-mode syntax highlighting."""
        theme = _normalize_syntax_theme(out_theme)
        operations: list[OutputOperation] = []
        for idx, value in enumerate(values):
            if idx > 0:
                operations.append(OutputOperation(kind="console_print", text="", markup=False))
            operations.append(
                OutputOperation(
                    kind="console_print",
                    renderable=Syntax(
                        _format_org_block(value),
                        "org",
                        theme=theme,
                        line_numbers=False,
                        word_wrap=True,
                    ),
                )
            )
        return PreparedOutput(operations=tuple(operations))


class _StubQueryOutputFormatter:
    """Placeholder formatter for non-org query output."""

    include_filenames = False

    def prepare(
        self, values: list[object], console: Console, color_enabled: bool, out_theme: str
    ) -> PreparedOutput:
        del values
        del console
        del color_enabled
        del out_theme
        return PreparedOutput(operations=())


class OutputFormatError(RuntimeError):
    """Raised when output formatting fails."""


def _write_plain_output(console: Console, text: str) -> None:
    """Write plain output directly to console stream."""
    console.file.write(f"{text}\n")
    console.file.flush()


def print_prepared_output(console: Console, prepared_output: PreparedOutput) -> None:
    """Print already prepared output operations."""
    for operation in prepared_output.operations:
        if operation.kind == "plain_write":
            if operation.text is not None:
                _write_plain_output(console, operation.text)
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
    base_output = normalized_output.split("+", 1)[0].split("-", 1)[0]
    language = _RENDERABLE_OUTPUT_FORMATS.get(normalized_output)
    if language is not None:
        return language
    return _RENDERABLE_OUTPUT_FORMATS.get(base_output)


def _normalize_syntax_theme(out_theme: str) -> str:
    """Return a valid theme name for syntax rendering."""
    normalized_theme = out_theme.strip()
    if normalized_theme:
        return normalized_theme
    return DEFAULT_OUTPUT_THEME


def _prepare_output(
    text: str,
    color_enabled: bool,
    output_format: str,
    out_theme: str,
) -> PreparedOutput:
    """Prepare output with syntax highlighting when available."""
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
        return str(value).rstrip()
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
    return "\n\n".join(non_empty_parts)


def _parse_pandoc_args(pandoc_args: str | None) -> list[str]:
    """Parse optional pandoc args string into argument list."""
    if pandoc_args is None or not pandoc_args.strip():
        return []
    try:
        return shlex.split(pandoc_args)
    except ValueError as exc:
        raise OutputFormatError(str(exc)) from exc


def _org_to_pandoc_format(org_text: str, output_format: str, pandoc_args: list[str]) -> str:
    """Convert org text into the requested output format using one pandoc invocation."""
    try:
        command = ["pandoc", "-f", "org", "-t", output_format, *pandoc_args]
        result = subprocess.run(
            command,
            input=org_text,
            text=True,
            capture_output=True,
            check=False,
        )
    except (OSError, ValueError) as exc:
        raise OutputFormatError(str(exc)) from exc

    stderr_text = result.stderr.strip()
    if result.returncode != 0:
        message = (
            stderr_text if stderr_text else f"pandoc failed with exit code {result.returncode}"
        )
        raise OutputFormatError(message)

    if stderr_text:
        for line in stderr_text.splitlines():
            logger.info("pandoc warning: %s", line)

    return result.stdout


class PandocQueryOutputFormatter:
    """Pandoc-based output formatter for query command."""

    include_filenames = False

    def __init__(self, output_format: str, pandoc_args: str | None) -> None:
        self.output_format = output_format
        self.pandoc_args = _parse_pandoc_args(pandoc_args)

    def prepare(
        self, values: list[object], console: Console, color_enabled: bool, out_theme: str
    ) -> PreparedOutput:
        del console
        formatted_text = _org_to_pandoc_format(
            _build_org_document(values),
            self.output_format,
            self.pandoc_args,
        )
        return _prepare_output(formatted_text, color_enabled, self.output_format, out_theme)


_NODE_EXCLUDED_FIELDS = {
    "body_rich",
    "children",
    "env",
    "next_same_level",
    "parent",
    "previous_same_level",
    "root",
}
_ROOT_EXCLUDED_FIELDS = {
    "body_rich",
    "children",
    "next_same_level",
    "parent",
    "previous_same_level",
    "root",
}
_ENV_EXCLUDED_FIELDS: set[str] = {"nodes"}
_DATE_EXCLUDED_FIELDS: set[str] = set()


def _is_primitive_json_type(value: object) -> bool:
    """Return whether the value maps directly to a JSON primitive."""
    return value is None or isinstance(value, bool | int | float | str)


def _iter_public_attributes(value: object) -> Iterable[tuple[str, object]]:
    """Yield public, non-callable attributes from an object."""
    for name in dir(value):
        if name.startswith("_"):
            continue
        try:
            attr_value = getattr(value, name)
        except AttributeError:
            continue
        except RuntimeError:
            continue
        except TypeError:
            continue
        except ValueError:
            continue
        if callable(attr_value):
            continue
        yield name, attr_value


def _org_object_to_json_dict(value: object, seen: set[int]) -> dict[str, object]:
    """Serialize org object public attributes into a JSON object."""
    excluded_fields = _DATE_EXCLUDED_FIELDS
    if isinstance(value, OrgRootNode):
        excluded_fields = _ROOT_EXCLUDED_FIELDS
    elif isinstance(value, orgparse.node.OrgNode):
        excluded_fields = _NODE_EXCLUDED_FIELDS
    elif isinstance(value, orgparse.node.OrgEnv):
        excluded_fields = _ENV_EXCLUDED_FIELDS

    data: dict[str, object] = {"type": type(value).__name__}
    for field_name, field_value in _iter_public_attributes(value):
        if field_name in excluded_fields:
            continue
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


class JsonQueryOutputFormatter:
    """JSON output formatter for query command."""

    include_filenames = False

    def prepare(
        self, values: list[object], console: Console, color_enabled: bool, out_theme: str
    ) -> PreparedOutput:
        del console
        return _prepare_output(
            json.dumps(_json_output_payload(values), ensure_ascii=True),
            color_enabled,
            OutputFormat.JSON,
            out_theme,
        )


def _format_short_task_list(
    nodes: list[orgparse.node.OrgNode],
    done_keys: list[str],
    todo_keys: list[str],
    color_enabled: bool,
    buckets: int,
) -> str:
    """Return formatted short list of tasks."""
    lines = [
        format_task_line(
            node,
            TaskLineConfig(
                color_enabled=color_enabled,
                done_keys=done_keys,
                todo_keys=todo_keys,
                buckets=buckets,
            ),
        )
        for node in nodes
    ]
    return lines_to_text(lines)


def _prepare_detailed_task_list(
    nodes: list[orgparse.node.OrgNode], out_theme: str
) -> PreparedOutput:
    """Prepare detailed list of tasks with syntax highlighting."""
    theme = _normalize_syntax_theme(out_theme)
    operations: list[OutputOperation] = []
    for idx, node in enumerate(nodes):
        if idx > 0:
            operations.append(OutputOperation(kind="console_print", text="", markup=False))
        filename = node.env.filename if hasattr(node, "env") and node.env.filename else "unknown"
        node_text = str(node).rstrip()
        org_block = f"# {filename}\n{node_text}" if node_text else f"# {filename}"
        operations.append(
            OutputOperation(
                kind="console_print",
                renderable=Syntax(
                    org_block, "org", theme=theme, line_numbers=False, word_wrap=True
                ),
            )
        )
    return PreparedOutput(operations=tuple(operations))


class OrgTasksListOutputFormatter:
    """Org output formatter for tasks list command."""

    include_filenames = True

    def prepare(self, data: TasksListRenderInput) -> PreparedOutput:
        if not data.nodes:
            return PreparedOutput(
                operations=(OutputOperation(kind="console_print", text="No results", markup=False),)
            )

        if data.details:
            return _prepare_detailed_task_list(data.nodes, data.out_theme)

        output = _format_short_task_list(
            data.nodes,
            data.done_keys,
            data.todo_keys,
            data.color_enabled,
            data.buckets,
        )
        if output:
            return PreparedOutput(
                operations=(
                    OutputOperation(
                        kind="print_output",
                        text=output,
                        color_enabled=data.color_enabled,
                        end="",
                    ),
                )
            )

        return PreparedOutput(
            operations=(OutputOperation(kind="console_print", text="No results", markup=False),)
        )


class _StubTasksListOutputFormatter:
    """Placeholder formatter for non-org tasks list output."""

    include_filenames = False

    def prepare(self, data: TasksListRenderInput) -> PreparedOutput:
        del data
        return PreparedOutput(operations=())


class PandocTasksListOutputFormatter:
    """Pandoc-based output formatter for tasks list command."""

    include_filenames = False

    def __init__(self, output_format: str, pandoc_args: str | None) -> None:
        self.output_format = output_format
        self.pandoc_args = _parse_pandoc_args(pandoc_args)

    def prepare(self, data: TasksListRenderInput) -> PreparedOutput:
        formatted_text = _org_to_pandoc_format(
            _build_org_document(list(data.nodes)),
            self.output_format,
            self.pandoc_args,
        )
        return _prepare_output(
            formatted_text,
            data.color_enabled,
            self.output_format,
            data.out_theme,
        )


class JsonTasksListOutputFormatter:
    """JSON output formatter for tasks list command."""

    include_filenames = False

    def prepare(self, data: TasksListRenderInput) -> PreparedOutput:
        payload = _json_output_payload(list(data.nodes))
        return _prepare_output(
            json.dumps(payload, ensure_ascii=True),
            data.color_enabled,
            OutputFormat.JSON,
            data.out_theme,
        )


_ORG_QUERY_FORMATTER = OrgQueryOutputFormatter()
_JSON_QUERY_FORMATTER = JsonQueryOutputFormatter()

_ORG_TASKS_LIST_FORMATTER = OrgTasksListOutputFormatter()
_JSON_TASKS_LIST_FORMATTER = JsonTasksListOutputFormatter()


def get_query_formatter(output_format: str, pandoc_args: str | None) -> QueryOutputFormatter:
    """Return query formatter for selected output format."""
    normalized_output = output_format.strip().lower()
    if normalized_output == OutputFormat.ORG:
        return _ORG_QUERY_FORMATTER
    if normalized_output == OutputFormat.JSON:
        return _JSON_QUERY_FORMATTER
    return PandocQueryOutputFormatter(normalized_output, pandoc_args)


def get_tasks_list_formatter(
    output_format: str, pandoc_args: str | None
) -> TasksListOutputFormatter:
    """Return tasks list formatter for selected output format."""
    normalized_output = output_format.strip().lower()
    if normalized_output == OutputFormat.ORG:
        return _ORG_TASKS_LIST_FORMATTER
    if normalized_output == OutputFormat.JSON:
        return _JSON_TASKS_LIST_FORMATTER
    return PandocTasksListOutputFormatter(normalized_output, pandoc_args)
