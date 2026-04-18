"""Tasks board command."""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

import typer
from rich import box
from rich.cells import cell_len
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from org import config as config_module
from org.cli_common import load_and_process_data
from org.color import escape_text, get_state_color
from org.tui import build_console, heading_title_to_text, processing_status, setup_output


if TYPE_CHECKING:
    from org_parser.document import Heading


@dataclass
class BoardArgs:
    """Arguments for the tasks board command."""

    files: list[str] | None
    config: str
    exclude: str | None
    mapping: str | None
    mapping_inline: dict[str, str] | None
    exclude_inline: list[str] | None
    todo_states: str
    done_states: str
    filter_priority: str | None
    filter_level: int | None
    filter_repeats_above: int | None
    filter_repeats_below: int | None
    filter_date_from: str | None
    filter_date_until: str | None
    filter_properties: list[str] | None
    filter_tags: list[str] | None
    filter_headings: list[str] | None
    filter_bodies: list[str] | None
    filter_completed: bool
    filter_not_completed: bool
    color_flag: bool | None
    width: int | None
    max_results: int | None
    offset: int
    order_by_level: bool
    order_by_file_order: bool
    order_by_file_order_reversed: bool
    order_by_priority: bool
    order_by_timestamp_asc: bool
    order_by_timestamp_desc: bool
    with_tags_as_category: bool
    coalesce_completed: bool


@dataclass(frozen=True)
class _BoardColumn:
    """One board column with title and assigned tasks."""

    title: str
    nodes: list[Heading]


@dataclass(frozen=True)
class _PanelRenderConfig:
    """Rendering context passed to task panel builders."""

    width: int
    color_enabled: bool
    done_states: list[str]
    todo_states: list[str]
    coalesce_completed: bool


def _state_prefix(
    node: Heading,
    done_states: list[str],
    todo_states: list[str],
    color_enabled: bool,
) -> Text:
    """Build a state prefix text fragment for a task panel title line."""
    state = node.todo or ""
    if not state:
        return Text("")
    style = get_state_color(state, done_states, todo_states, color_enabled)
    if color_enabled and style:
        return Text(f"{state} ", style=style)
    return Text(f"{state} ")


def _task_metadata_text(node: Heading, color_enabled: bool) -> Text:
    """Build priority and tags metadata text for one task panel."""
    meta = Text("")

    if node.priority:
        if color_enabled:
            meta.append(f"[#{node.priority}]", style="bold blue")
        else:
            meta.append(f"[#{node.priority}]")

    if node.tags:
        if meta.plain:
            meta.append(" ")
        tags_text = f":{':'.join(sorted(node.tags))}:"
        if color_enabled:
            meta.append(tags_text, style="dim white")
        else:
            meta.append(tags_text)

    return meta


def _build_task_panel(node: Heading, render: _PanelRenderConfig) -> Panel:
    """Build a visual panel for one task."""
    content = Text("")

    if render.coalesce_completed and node.todo and node.todo in render.done_states:
        content.append_text(
            _state_prefix(node, render.done_states, render.todo_states, render.color_enabled),
        )

    content.append_text(heading_title_to_text(node))

    meta = _task_metadata_text(node, render.color_enabled)
    if meta.plain:
        content.append("\n")
        content.append_text(meta)

    return Panel(content, expand=True, box=box.ROUNDED, padding=(0, 1))


def _completed_header_state(done_states: list[str]) -> str:
    """Resolve representative completed state for header coloring."""
    non_cancelled = [key for key in done_states if key != "CANCELLED"]
    if non_cancelled:
        return non_cancelled[0]
    if done_states:
        return done_states[0]
    return "DONE"


def _column_title_markup(
    title: str,
    state: str,
    done_states: list[str],
    todo_states: list[str],
    color_enabled: bool,
) -> str:
    """Build column title with state-aligned coloring."""
    style = get_state_color(state, done_states, todo_states, color_enabled)
    safe_title = escape_text(title, color_enabled)
    if color_enabled and style:
        return f"[{style}]{safe_title}[/]"
    return safe_title


def _initial_columns(
    todo_states: list[str],
    done_states: list[str],
    coalesce_completed: bool,
) -> dict[str, list[Heading]]:
    """Create mutable board columns keyed by title."""
    columns: dict[str, list[Heading]] = {"NOT STARTED": []}
    for key in todo_states:
        columns[key] = []
    if coalesce_completed:
        columns["COMPLETED"] = []
    else:
        for key in done_states:
            columns[key] = []
    return columns


def _place_node(
    columns: dict[str, list[Heading]],
    node: Heading,
    todo_states: list[str],
    done_states: list[str],
    coalesce_completed: bool,
) -> None:
    """Assign one node to its board column."""
    state = node.todo
    if not state:
        columns["NOT STARTED"].append(node)
        return
    if state in done_states:
        if coalesce_completed:
            columns["COMPLETED"].append(node)
        else:
            columns[state].append(node)
        return
    if state in todo_states:
        columns[state].append(node)
        return
    columns["NOT STARTED"].append(node)


def _build_board_columns(
    nodes: list[Heading],
    todo_states: list[str],
    done_states: list[str],
    coalesce_completed: bool,
) -> list[_BoardColumn]:
    """Group nodes into ordered board columns."""
    columns = _initial_columns(todo_states, done_states, coalesce_completed)
    for node in nodes:
        _place_node(columns, node, todo_states, done_states, coalesce_completed)
    if coalesce_completed:
        ordered_titles = ["NOT STARTED", *todo_states, "COMPLETED"]
    else:
        ordered_titles = ["NOT STARTED", *todo_states, *done_states]
    return [_BoardColumn(title=title, nodes=columns[title]) for title in ordered_titles]


def _estimate_panel_content_width(console_width: int, column_count: int) -> int:
    """Estimate panel inner width for pre-wrapping task card lines."""
    safe_columns = max(1, column_count)
    raw_width = console_width // safe_columns
    return max(10, raw_width - 8)


def _resolve_tasks_limit(max_results: int | None) -> int:
    """Resolve effective tasks limit, defaulting to all available tasks."""
    if max_results is None:
        return sys.maxsize
    return max_results


def _task_panel_height(node: Heading, width: int) -> int:
    """Estimate panel height for one task card."""
    heading_width = cell_len(heading_title_to_text(node).plain)
    heading_lines = max(1, math.ceil(heading_width / max(1, width)))
    has_metadata = bool(node.priority or node.tags)
    return heading_lines + (1 if has_metadata else 0) + 2


def _column_content_height(nodes: list[Heading], width: int) -> int:
    """Estimate rendered content height for one board column."""
    if not nodes:
        return 1
    return sum(_task_panel_height(node, width) for node in nodes)


def _estimate_board_height(columns: list[_BoardColumn], panel_content_width: int) -> int:
    """Estimate total rendered board table height in terminal lines."""
    column_heights = [
        _column_content_height(column.nodes, panel_content_width) for column in columns
    ]
    content_row_height = max(column_heights, default=1)
    return content_row_height + 3


def _resolve_header_state(
    column: _BoardColumn,
    done_states: list[str],
    coalesce_completed: bool,
) -> str:
    """Resolve the state name used for coloring a column header."""
    if column.title == "NOT STARTED":
        return ""
    if coalesce_completed and column.title == "COMPLETED":
        return _completed_header_state(done_states)
    return column.title


def _restore_key_order(specified: list[str], discovered: list[str]) -> list[str]:
    """Return discovered keys with user-specified keys first in their original order."""
    specified_set = set(specified)
    extras = [k for k in discovered if k not in specified_set]
    return [*specified, *extras]


def run_tasks_board(args: BoardArgs) -> None:
    """Run the tasks board command."""
    color_enabled = setup_output(args)
    console = build_console(color_enabled, args.width)
    if console.width < 80:
        raise typer.BadParameter("--width must be at least 80")
    if args.offset < 0:
        raise typer.BadParameter("--offset must be non-negative")
    if args.max_results is not None and args.max_results < 0:
        raise typer.BadParameter("--limit must be non-negative")
    args.max_results = _resolve_tasks_limit(args.max_results)

    table = Table(expand=True, box=box.SQUARE, show_lines=False, show_header=False)
    board_height = 0

    with processing_status(console, color_enabled):
        nodes, discovered_todo_states, discovered_done_states = load_and_process_data(args)

        specified_todo_states = [k.strip() for k in args.todo_states.split(",") if k.strip()]
        specified_done_states = [k.strip() for k in args.done_states.split(",") if k.strip()]
        todo_states = _restore_key_order(specified_todo_states, discovered_todo_states)
        done_states = _restore_key_order(specified_done_states, discovered_done_states)

        if not nodes:
            console.print("No results", markup=False)
            return

        columns = _build_board_columns(nodes, todo_states, done_states, args.coalesce_completed)
        panel_content_width = _estimate_panel_content_width(console.width, len(columns))

        for _ in columns:
            table.add_column(ratio=1)

        header_row: list[str] = []
        for column in columns:
            state = _resolve_header_state(column, done_states, args.coalesce_completed)
            header_row.append(
                _column_title_markup(column.title, state, done_states, todo_states, color_enabled),
            )
        table.add_row(*header_row)

        render = _PanelRenderConfig(
            width=panel_content_width,
            color_enabled=color_enabled,
            done_states=done_states,
            todo_states=todo_states,
            coalesce_completed=args.coalesce_completed,
        )
        content_cells: list[RenderableType] = []
        for column in columns:
            if not column.nodes:
                content_cells.append(Text(""))
                continue
            panels = [_build_task_panel(node, render) for node in column.nodes]
            content_cells.append(Group(*panels))

        table.add_row(*content_cells)
        board_height = _estimate_board_height(columns, panel_content_width)

    if board_height > console.height:
        with console.pager(styles=color_enabled):
            console.print(table)
        return

    console.print(table)


def register(app: typer.Typer) -> None:
    """Register the tasks board command."""

    @app.command(
        "board",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )
    def tasks_board(  # noqa: PLR0913
        files: list[str] | None = typer.Argument(  # noqa: B008
            None,
            metavar="FILE",
            help="Org-mode archive files or directories to analyze",
        ),
        config: str = typer.Option(
            ".org-cli.json",
            "--config",
            metavar="FILE",
            help="Config file name to load from current directory",
        ),
        exclude: str | None = typer.Option(
            None,
            "--exclude",
            metavar="FILE",
            help="File containing words to exclude (one per line)",
        ),
        mapping: str | None = typer.Option(
            None,
            "--mapping",
            metavar="FILE",
            help="JSON file containing tag mappings (dict[str, str])",
        ),
        todo_states: str = typer.Option(
            "TODO",
            "--todo-states",
            metavar="KEYS",
            help="Comma-separated list of incomplete task states",
        ),
        done_states: str = typer.Option(
            "DONE",
            "--done-states",
            metavar="KEYS",
            help="Comma-separated list of completed task states",
        ),
        filter_priority: str | None = typer.Option(
            None,
            "--filter-priority",
            metavar="P",
            help="Filter tasks where priority equals P",
        ),
        filter_level: int | None = typer.Option(
            None,
            "--filter-level",
            metavar="N",
            help="Filter tasks where heading level equals N",
        ),
        filter_repeats_above: int | None = typer.Option(
            None,
            "--filter-repeats-above",
            metavar="N",
            help="Filter tasks where repeat count > N (non-inclusive)",
        ),
        filter_repeats_below: int | None = typer.Option(
            None,
            "--filter-repeats-below",
            metavar="N",
            help="Filter tasks where repeat count < N (non-inclusive)",
        ),
        filter_date_from: str | None = typer.Option(
            None,
            "--filter-date-from",
            metavar="TIMESTAMP",
            help=(
                "Filter tasks with timestamps after date (inclusive). "
                "Formats: YYYY-MM-DD, YYYY-MM-DDThh:mm, YYYY-MM-DDThh:mm:ss, "
                "YYYY-MM-DD hh:mm, YYYY-MM-DD hh:mm:ss"
            ),
        ),
        filter_date_until: str | None = typer.Option(
            None,
            "--filter-date-until",
            metavar="TIMESTAMP",
            help=(
                "Filter tasks with timestamps before date (inclusive). "
                "Formats: YYYY-MM-DD, YYYY-MM-DDThh:mm, YYYY-MM-DDThh:mm:ss, "
                "YYYY-MM-DD hh:mm, YYYY-MM-DD hh:mm:ss"
            ),
        ),
        filter_properties: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--filter-property",
            metavar="KEY=VALUE",
            help="Filter tasks with exact property match (case-sensitive, can specify multiple)",
        ),
        filter_tags: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--filter-tag",
            metavar="REGEX",
            help="Filter tasks where any tag matches regex (case-sensitive, can specify multiple)",
        ),
        filter_headings: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--filter-heading",
            metavar="REGEX",
            help="Filter tasks where heading matches regex (case-sensitive, can specify multiple)",
        ),
        filter_bodies: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--filter-body",
            metavar="REGEX",
            help=(
                "Filter tasks where body matches regex (case-sensitive, multiline, "
                "can specify multiple)"
            ),
        ),
        filter_completed: bool = typer.Option(
            False,
            "--filter-completed",
            help="Filter tasks with todo state in done keys",
        ),
        filter_not_completed: bool = typer.Option(
            False,
            "--filter-not-completed",
            help="Filter tasks with todo state in todo keys or without a todo state",
        ),
        color_flag: bool | None = typer.Option(
            None,
            "--color/--no-color",
            help="Force colored output",
        ),
        width: int | None = typer.Option(
            None,
            "--width",
            metavar="N",
            min=80,
            help="Override auto-derived console width (minimum: 80)",
        ),
        max_results: int | None = typer.Option(
            None,
            "--limit",
            "-n",
            metavar="N",
            help="Maximum number of results to display (defaults to all results)",
        ),
        offset: int = typer.Option(
            0,
            "--offset",
            metavar="N",
            help="Number of results to skip before displaying",
        ),
        order_by_level: bool = typer.Option(
            False,
            "--order-by-level",
            help="Order tasks by heading level (repeatable)",
        ),
        order_by_file_order: bool = typer.Option(
            False,
            "--order-by-file-order",
            help="Keep tasks in source file order (repeatable)",
        ),
        order_by_file_order_reversed: bool = typer.Option(
            False,
            "--order-by-file-order-reversed",
            help="Reverse source file order (repeatable)",
        ),
        order_by_priority: bool = typer.Option(
            False,
            "--order-by-priority",
            help="Order by priority (repeatable)",
        ),
        order_by_timestamp_asc: bool = typer.Option(
            False,
            "--order-by-timestamp-asc",
            help="Order by oldest timestamp first (repeatable)",
        ),
        order_by_timestamp_desc: bool = typer.Option(
            False,
            "--order-by-timestamp-desc",
            help="Order by newest timestamp first (repeatable)",
        ),
        with_tags_as_category: bool = typer.Option(
            False,
            "--with-tags-as-category",
            help="Preprocess nodes to set category from first tag",
        ),
        coalesce_completed: bool = typer.Option(
            True,
            "--coalesce-completed/--no-coalesce-completed",
            help=(
                "Coalesce all completed states into a single COMPLETED column. "
                "When disabled, each done state gets its own column."
            ),
        ),
    ) -> None:
        """Display tasks as an AGILE-style board."""
        args = BoardArgs(
            files=files,
            config=config,
            exclude=exclude,
            mapping=mapping,
            mapping_inline=None,
            exclude_inline=None,
            todo_states=todo_states,
            done_states=done_states,
            filter_priority=filter_priority,
            filter_level=filter_level,
            filter_repeats_above=filter_repeats_above,
            filter_repeats_below=filter_repeats_below,
            filter_date_from=filter_date_from,
            filter_date_until=filter_date_until,
            filter_properties=filter_properties,
            filter_tags=filter_tags,
            filter_headings=filter_headings,
            filter_bodies=filter_bodies,
            filter_completed=filter_completed,
            filter_not_completed=filter_not_completed,
            color_flag=color_flag,
            width=width,
            max_results=max_results,
            offset=offset,
            order_by_level=order_by_level,
            order_by_file_order=order_by_file_order,
            order_by_file_order_reversed=order_by_file_order_reversed,
            order_by_priority=order_by_priority,
            order_by_timestamp_asc=order_by_timestamp_asc,
            order_by_timestamp_desc=order_by_timestamp_desc,
            with_tags_as_category=with_tags_as_category,
            coalesce_completed=coalesce_completed,
        )
        config_module.apply_config_defaults(args)
        config_module.log_applied_config_defaults(args, sys.argv[1:], "tasks board")
        config_module.log_command_arguments(args, "tasks board")
        run_tasks_board(args)
