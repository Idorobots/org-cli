"""Output format abstraction and format-specific renderers."""

from __future__ import annotations

import json
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


class OutputFormat(StrEnum):
    """Supported output formats."""

    ORG = "org"
    MD = "md"
    JSON = "json"


class QueryOutputFormatter(Protocol):
    """Formatter interface for the query command."""

    include_filenames: bool

    def render(self, values: list[object], console: Console, color_enabled: bool) -> None:
        """Render query output values."""


class TasksListOutputFormatter(Protocol):
    """Formatter interface for the tasks list command."""

    include_filenames: bool

    def render(self, data: TasksListRenderInput) -> None:
        """Render tasks list output."""


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

    def render(self, values: list[object], console: Console, color_enabled: bool) -> None:
        del color_enabled
        if values and all(_is_org_object(value) for value in values):
            self._render_org_values(values, console)
            return

        lines = [_format_query_value(value) for value in values]
        if not lines:
            console.print("No results", markup=False)
            return

        for line in lines:
            console.print(line, markup=False)

    def _render_org_values(self, values: list[object], console: Console) -> None:
        """Render org values using org-mode syntax highlighting."""
        for idx, value in enumerate(values):
            if idx > 0:
                console.print()
            console.print(
                Syntax(_format_org_block(value), "org", line_numbers=False, word_wrap=False)
            )


class _StubQueryOutputFormatter:
    """Placeholder formatter for non-org query output."""

    include_filenames = False

    def render(self, values: list[object], console: Console, color_enabled: bool) -> None:
        del values
        del console
        del color_enabled


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
_ENV_EXCLUDED_FIELDS: set[str] = set()
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

    def render(self, values: list[object], console: Console, color_enabled: bool) -> None:
        del color_enabled
        console.file.write(f"{json.dumps(_json_output_payload(values), ensure_ascii=True)}\n")
        console.file.flush()


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


def _render_detailed_task_list(nodes: list[orgparse.node.OrgNode], console: Console) -> None:
    """Render detailed list of tasks with syntax highlighting."""
    for idx, node in enumerate(nodes):
        if idx > 0:
            console.print()
        filename = node.env.filename if hasattr(node, "env") and node.env.filename else "unknown"
        node_text = str(node).rstrip()
        org_block = f"# {filename}\n{node_text}" if node_text else f"# {filename}"
        console.print(Syntax(org_block, "org", line_numbers=False, word_wrap=False))


class OrgTasksListOutputFormatter:
    """Org output formatter for tasks list command."""

    include_filenames = True

    def render(self, data: TasksListRenderInput) -> None:
        if not data.nodes:
            data.console.print("No results", markup=False)
            return

        if data.details:
            _render_detailed_task_list(data.nodes, data.console)
            return

        output = _format_short_task_list(
            data.nodes,
            data.done_keys,
            data.todo_keys,
            data.color_enabled,
            data.buckets,
        )
        if output:
            print_output(data.console, output, data.color_enabled, end="")
            return

        data.console.print("No results", markup=False)


class _StubTasksListOutputFormatter:
    """Placeholder formatter for non-org tasks list output."""

    include_filenames = False

    def render(self, data: TasksListRenderInput) -> None:
        del data


class JsonTasksListOutputFormatter:
    """JSON output formatter for tasks list command."""

    include_filenames = False

    def render(self, data: TasksListRenderInput) -> None:
        payload = _json_output_payload(list(data.nodes))
        data.console.file.write(f"{json.dumps(payload, ensure_ascii=True)}\n")
        data.console.file.flush()


_ORG_QUERY_FORMATTER = OrgQueryOutputFormatter()
_MD_QUERY_FORMATTER = _StubQueryOutputFormatter()
_JSON_QUERY_FORMATTER = JsonQueryOutputFormatter()

_ORG_TASKS_LIST_FORMATTER = OrgTasksListOutputFormatter()
_MD_TASKS_LIST_FORMATTER = _StubTasksListOutputFormatter()
_JSON_TASKS_LIST_FORMATTER = JsonTasksListOutputFormatter()


def get_query_formatter(output_format: OutputFormat) -> QueryOutputFormatter:
    """Return query formatter for selected output format."""
    if output_format is OutputFormat.ORG:
        return _ORG_QUERY_FORMATTER
    if output_format is OutputFormat.MD:
        return _MD_QUERY_FORMATTER
    return _JSON_QUERY_FORMATTER


def get_tasks_list_formatter(output_format: OutputFormat) -> TasksListOutputFormatter:
    """Return tasks list formatter for selected output format."""
    if output_format is OutputFormat.ORG:
        return _ORG_TASKS_LIST_FORMATTER
    if output_format is OutputFormat.MD:
        return _MD_TASKS_LIST_FORMATTER
    return _JSON_TASKS_LIST_FORMATTER
