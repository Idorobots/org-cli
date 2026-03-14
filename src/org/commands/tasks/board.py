"""Tasks board command."""

from __future__ import annotations

import sys
import textwrap
from dataclasses import dataclass

import orgparse
import typer
from rich import box
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from org import config as config_module
from org.cli_common import load_and_process_data
from org.color import bright_blue, dim_white, escape_text, get_state_color
from org.tui import build_console, processing_status, setup_output


@dataclass
class BoardArgs:
    """Arguments for the tasks board command."""

    files: list[str] | None
    config: str
    exclude: str | None
    mapping: str | None
    mapping_inline: dict[str, str] | None
    exclude_inline: list[str] | None
    todo_keys: str
    done_keys: str
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
    category_property: str


@dataclass(frozen=True)
class _BoardColumn:
    """One board column with title and assigned tasks."""

    title: str
    nodes: list[orgparse.node.OrgNode]


def _build_heading_lines(node: orgparse.node.OrgNode, width: int, color_enabled: bool) -> list[str]:
    """Build wrapped heading lines for one task panel."""
    heading = node.heading if node.heading else ""
    escaped_heading = escape_text(heading, color_enabled)
    lines = textwrap.wrap(
        escaped_heading,
        width=max(10, width),
        break_long_words=False,
        break_on_hyphens=False,
    )
    return lines or [""]


def _build_wrapped_tag_lines(tags: set[str], width: int) -> list[str]:
    """Wrap tags preserving boundaries between tag names."""
    if not tags:
        return []

    max_width = max(4, width)
    wrapped: list[str] = []
    current = ":"
    for tag in sorted(tags):
        candidate = f"{tag}:"
        if len(current) + len(candidate) <= max_width:
            current = f"{current}{candidate}"
            continue
        if current == ":":
            current = f":{candidate}"
            continue
        wrapped.append(current)
        current = f":{candidate}"

    wrapped.append(current)
    return wrapped


def _build_metadata_lines(
    node: orgparse.node.OrgNode, width: int, color_enabled: bool
) -> list[str]:
    """Build styled metadata lines for priority and tags."""
    priority_text = f"[#{node.priority}]" if node.priority else ""
    tag_lines = _build_wrapped_tag_lines(set(node.tags), width)

    if not priority_text and not tag_lines:
        return []

    if priority_text and not tag_lines:
        return [bright_blue(priority_text, color_enabled)]

    if not priority_text and tag_lines:
        return [dim_white(line, color_enabled) for line in tag_lines]

    first_tag_line = tag_lines[0]
    first_line = (
        f"{bright_blue(priority_text, color_enabled)} {dim_white(first_tag_line, color_enabled)}"
    )
    continuation = [dim_white(line, color_enabled) for line in tag_lines[1:]]
    return [first_line, *continuation]


def _build_task_panel(node: orgparse.node.OrgNode, width: int, color_enabled: bool) -> Panel:
    """Build a visual panel for one task."""
    title_lines = _build_heading_lines(node, width, color_enabled)
    metadata_lines = _build_metadata_lines(node, width, color_enabled)
    lines = [*title_lines, *metadata_lines]
    return Panel(
        Text.from_markup("\n".join(lines)) if color_enabled else Text("\n".join(lines)),
        expand=True,
        box=box.ROUNDED,
        padding=(0, 1),
    )


def _completed_header_state(done_keys: list[str]) -> str:
    """Resolve representative completed state for header coloring."""
    non_cancelled = [key for key in done_keys if key != "CANCELLED"]
    if non_cancelled:
        return non_cancelled[0]
    if done_keys:
        return done_keys[0]
    return "DONE"


def _column_title_markup(
    title: str,
    state: str,
    done_keys: list[str],
    todo_keys: list[str],
    color_enabled: bool,
) -> str:
    """Build column title with state-aligned coloring."""
    style = get_state_color(state, done_keys, todo_keys, color_enabled)
    safe_title = escape_text(title, color_enabled)
    if color_enabled and style:
        return f"[{style}]{safe_title}[/]"
    return safe_title


def _initial_columns(todo_keys: list[str]) -> dict[str, list[orgparse.node.OrgNode]]:
    """Create mutable board columns keyed by title."""
    columns: dict[str, list[orgparse.node.OrgNode]] = {"NOT STARTED": []}
    for key in todo_keys:
        columns[key] = []
    columns["COMPLETED"] = []
    return columns


def _place_node(
    columns: dict[str, list[orgparse.node.OrgNode]],
    node: orgparse.node.OrgNode,
    todo_keys: list[str],
    done_keys: list[str],
) -> None:
    """Assign one node to its board column."""
    state = node.todo
    if not state:
        columns["NOT STARTED"].append(node)
        return
    if state in done_keys:
        columns["COMPLETED"].append(node)
        return
    if state in todo_keys:
        columns[state].append(node)
        return
    columns["NOT STARTED"].append(node)


def _build_board_columns(
    nodes: list[orgparse.node.OrgNode],
    todo_keys: list[str],
    done_keys: list[str],
) -> list[_BoardColumn]:
    """Group nodes into ordered board columns."""
    columns = _initial_columns(todo_keys)
    for node in nodes:
        _place_node(columns, node, todo_keys, done_keys)
    ordered_titles = ["NOT STARTED", *todo_keys, "COMPLETED"]
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


def _task_panel_height(node: orgparse.node.OrgNode, width: int, color_enabled: bool) -> int:
    """Estimate panel height for one task card."""
    title_lines = _build_heading_lines(node, width, color_enabled)
    metadata_lines = _build_metadata_lines(node, width, color_enabled)
    return len(title_lines) + len(metadata_lines) + 2


def _column_content_height(
    nodes: list[orgparse.node.OrgNode], width: int, color_enabled: bool
) -> int:
    """Estimate rendered content height for one board column."""
    if not nodes:
        return 1
    return sum(_task_panel_height(node, width, color_enabled) for node in nodes)


def _estimate_board_height(
    columns: list[_BoardColumn], panel_content_width: int, color_enabled: bool
) -> int:
    """Estimate total rendered board table height in terminal lines."""
    column_heights = [
        _column_content_height(column.nodes, panel_content_width, color_enabled)
        for column in columns
    ]
    content_row_height = max(column_heights, default=1)
    return content_row_height + 3


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

    with processing_status(console, color_enabled):
        nodes, todo_keys, done_keys = load_and_process_data(args)

    if not nodes:
        console.print("No results", markup=False)
        return

    columns = _build_board_columns(nodes, todo_keys, done_keys)
    panel_content_width = _estimate_panel_content_width(console.width, len(columns))

    table = Table(expand=True, box=box.SQUARE, show_lines=False, show_header=False)
    for _ in columns:
        table.add_column(ratio=1)

    header_row: list[str] = []
    for column in columns:
        state = column.title
        if column.title == "NOT STARTED":
            state = ""
        elif column.title == "COMPLETED":
            state = _completed_header_state(done_keys)

        header_row.append(
            _column_title_markup(column.title, state, done_keys, todo_keys, color_enabled)
        )
    table.add_row(*header_row)

    content_cells: list[RenderableType] = []
    for column in columns:
        if not column.nodes:
            content_cells.append(Text(""))
            continue
        panels = [
            _build_task_panel(node, panel_content_width, color_enabled) for node in column.nodes
        ]
        content_cells.append(Group(*panels))

    table.add_row(*content_cells)
    board_height = _estimate_board_height(columns, panel_content_width, color_enabled)
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
            None, metavar="FILE", help="Org-mode archive files or directories to analyze"
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
        todo_keys: str = typer.Option(
            "TODO",
            "--todo-keys",
            metavar="KEYS",
            help="Comma-separated list of incomplete task states",
        ),
        done_keys: str = typer.Option(
            "DONE",
            "--done-keys",
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
            help="Filter tasks where body matches regex (case-sensitive, multiline, can specify multiple)",
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
            help="Preprocess nodes to set category property based on first tag",
        ),
        category_property: str = typer.Option(
            "CATEGORY",
            "--category-property",
            metavar="PROPERTY",
            help="Property name to use for category histogram and filtering",
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
            todo_keys=todo_keys,
            done_keys=done_keys,
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
            category_property=category_property,
        )
        config_module.apply_config_defaults(args)
        config_module.log_applied_config_defaults(args, sys.argv[1:], "tasks board")
        config_module.log_command_arguments(args, "tasks board")
        run_tasks_board(args)
