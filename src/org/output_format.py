"""Output format abstraction and format-specific renderers."""

from __future__ import annotations

from dataclasses import dataclass
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


_ORG_QUERY_FORMATTER = OrgQueryOutputFormatter()
_MD_QUERY_FORMATTER = _StubQueryOutputFormatter()
_JSON_QUERY_FORMATTER = _StubQueryOutputFormatter()

_ORG_TASKS_LIST_FORMATTER = OrgTasksListOutputFormatter()
_MD_TASKS_LIST_FORMATTER = _StubTasksListOutputFormatter()
_JSON_TASKS_LIST_FORMATTER = _StubTasksListOutputFormatter()


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
