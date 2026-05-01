"""Board command."""

from __future__ import annotations

import logging
import math
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

import typer
from rich import box
from rich.cells import cell_len
from rich.console import Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from org import config as config_module
from org.cli_common import load_and_process_data
from org.color import escape_text, get_state_color
from org.commands.agenda import _advance_timestamp_by_repeater
from org.commands.interactive_common import (
    HeadingIdentity,
    KeyBinding,
    append_repeat_transition,
    dispatch_key_binding,
    heading_identity,
    heading_identity_matches,
    key_binding_for_action,
    key_binding_requires_live_pause,
    local_now,
    open_task_detail_in_pager,
    read_keypress,
    set_mouse_reporting,
    shift_priority,
)
from org.commands.tasks.common import save_document
from org.tui import (
    build_console,
    heading_title_to_text,
    processing_status,
    setup_output,
    task_priority_to_text,
    task_state_prefix_to_text,
    task_tags_to_text,
)


if TYPE_CHECKING:
    from org_parser.document import Document, Heading
    from rich.console import Console


logger = logging.getLogger("org")
_HIGHLIGHT_PANEL_STYLE = "on grey23"
_INTERACTIVE_HEADER_HEIGHT = 2
_INTERACTIVE_FOOTER_HEIGHT = 3
_INTERACTIVE_PANEL_HEIGHT = 4


@dataclass
class BoardArgs:
    """Arguments for the board command."""

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
class _BoardPanelRenderConfig:
    """Rendering context passed to task panel builders."""

    width: int
    color_enabled: bool
    done_states: list[str]
    todo_states: list[str]
    coalesce_completed: bool


@dataclass
class _BoardSession:
    """Interactive board session state."""

    args: BoardArgs
    nodes: list[Heading]
    todo_states: list[str]
    done_states: list[str]
    columns: list[_BoardColumn]
    color_enabled: bool
    selected_column_index: int
    selected_row_index: int
    scroll_offset: int
    status_message: str


@dataclass(frozen=True)
class _BoardStaticRenderInput:
    """Rendering input for non-interactive board output."""

    done_states: list[str]
    todo_states: list[str]
    color_enabled: bool
    coalesce_completed: bool


_BoardHeadingIdentity = HeadingIdentity


def _priority_rank(priority: str | None) -> int:
    """Return sort rank for board priority ordering."""
    rank = {"A": 0, "B": 1, "C": 2}
    return rank.get(priority or "", 3)


def _state_prefix(
    node: Heading,
    done_states: list[str],
    todo_states: list[str],
    color_enabled: bool,
) -> Text:
    """Build a state prefix text fragment for a task panel title line."""
    state = node.todo or ""
    return task_state_prefix_to_text(
        state,
        done_states=done_states,
        todo_states=todo_states,
        color_enabled=color_enabled,
    )


def _task_metadata_text(node: Heading, color_enabled: bool) -> Text:
    """Build priority and tags metadata text for one task panel."""
    meta = Text("")
    meta.append_text(
        task_priority_to_text(
            node.priority,
            color_enabled,
            trailing_space=bool(node.tags),
        ),
    )
    meta.append_text(task_tags_to_text(node.tags, color_enabled))
    return meta


def _build_task_panel(
    node: Heading,
    render: _BoardPanelRenderConfig,
    *,
    highlighted: bool,
) -> Panel:
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

    panel_style = _HIGHLIGHT_PANEL_STYLE if highlighted else ""
    border_style = "grey70" if highlighted and render.color_enabled else ""
    return Panel(
        content,
        expand=True,
        box=box.ROUNDED,
        padding=(0, 1),
        style=panel_style,
        border_style=border_style,
    )


def _heading_and_meta_lines(node: Heading, render: _BoardPanelRenderConfig) -> tuple[int, int]:
    """Estimate wrapped line counts for panel heading and metadata."""
    heading = Text("")
    if render.coalesce_completed and node.todo and node.todo in render.done_states:
        heading.append_text(
            _state_prefix(node, render.done_states, render.todo_states, color_enabled=False),
        )
    heading.append_text(heading_title_to_text(node))
    heading_lines = max(1, math.ceil(cell_len(heading.plain) / max(1, render.width)))

    metadata = _task_metadata_text(node, color_enabled=False)
    metadata_lines = 0
    if metadata.plain:
        metadata_lines = max(1, math.ceil(cell_len(metadata.plain) / max(1, render.width)))

    return heading_lines, metadata_lines


def _interactive_panel_height(node: Heading, render: _BoardPanelRenderConfig) -> int:
    """Estimate interactive panel height for one node."""
    heading_lines, metadata_lines = _heading_and_meta_lines(node, render)
    return heading_lines + metadata_lines + 2


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
    """Create mutable flow board columns keyed by title."""
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
    """Assign one node to its flow board column."""
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


def _build_flow_board_columns(
    nodes: list[Heading],
    todo_states: list[str],
    done_states: list[str],
    coalesce_completed: bool,
) -> list[_BoardColumn]:
    """Group nodes into ordered flow board columns."""
    columns = _initial_columns(todo_states, done_states, coalesce_completed)
    for node in nodes:
        _place_node(columns, node, todo_states, done_states, coalesce_completed)
    if coalesce_completed:
        ordered_titles = ["NOT STARTED", *todo_states, "COMPLETED"]
    else:
        ordered_titles = ["NOT STARTED", *todo_states, *done_states]

    output_columns: list[_BoardColumn] = []
    for title in ordered_titles:
        sorted_nodes = sorted(columns[title], key=lambda node: _priority_rank(node.priority))
        output_columns.append(_BoardColumn(title=title, nodes=sorted_nodes))
    return output_columns


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
    """Estimate rendered content height for one flow board column."""
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


def _specified_states(args: BoardArgs) -> tuple[list[str], list[str]]:
    """Return explicitly requested todo/done state lists."""
    specified_todo_states = [k.strip() for k in args.todo_states.split(",") if k.strip()]
    specified_done_states = [k.strip() for k in args.done_states.split(",") if k.strip()]
    return specified_todo_states, specified_done_states


def _resolved_states(
    args: BoardArgs,
    discovered_todo_states: list[str],
    discovered_done_states: list[str],
) -> tuple[list[str], list[str]]:
    """Resolve visible flow board states from configured and discovered states."""
    specified_todo_states, specified_done_states = _specified_states(args)
    todo_states = _restore_key_order(specified_todo_states, discovered_todo_states)
    done_states = _restore_key_order(specified_done_states, discovered_done_states)
    return todo_states, done_states


def _render_static_flow_board(
    console: Console,
    columns: list[_BoardColumn],
    render_input: _BoardStaticRenderInput,
) -> None:
    """Render non-interactive flow board output."""
    table = Table(expand=True, box=box.SQUARE, show_lines=False, show_header=False)
    for _ in columns:
        table.add_column(ratio=1)

    header_row: list[str] = []
    for column in columns:
        state = _resolve_header_state(
            column,
            render_input.done_states,
            render_input.coalesce_completed,
        )
        header_row.append(
            _column_title_markup(
                column.title,
                state,
                render_input.done_states,
                render_input.todo_states,
                render_input.color_enabled,
            ),
        )
    table.add_row(*header_row)

    panel_content_width = _estimate_panel_content_width(console.width, len(columns))
    render = _BoardPanelRenderConfig(
        width=panel_content_width,
        color_enabled=render_input.color_enabled,
        done_states=render_input.done_states,
        todo_states=render_input.todo_states,
        coalesce_completed=render_input.coalesce_completed,
    )
    content_cells: list[RenderableType] = []
    for column in columns:
        if not column.nodes:
            content_cells.append(Text(""))
            continue
        panels = [_build_task_panel(node, render, highlighted=False) for node in column.nodes]
        content_cells.append(Group(*panels))
    table.add_row(*content_cells)

    board_height = _estimate_board_height(columns, panel_content_width)
    if board_height > console.height:
        with console.pager(styles=render_input.color_enabled):
            console.print(table)
        return

    console.print(table)


def _save_document_changes(document: Document) -> None:
    """Persist one mutated document to disk."""
    logger.info("Saving flow board edit file: %s", document.filename)
    document.sync_heading_id_index()
    save_document(document)


def _choose_done_state(console: Console, done_states: list[str]) -> str | None:
    """Prompt for a done state when moving into COMPLETED lane."""
    if not done_states:
        return None

    console.print("Choose completed state:")
    for idx, state in enumerate(done_states, start=1):
        console.print(f"{idx}) {state}")

    selection = console.input("State number or value (blank cancels): ").strip()
    if not selection:
        return None

    if selection.isdigit():
        index = int(selection) - 1
        if 0 <= index < len(done_states):
            return done_states[index]
        return None

    if selection in done_states:
        return selection
    return None


def _choose_target_state_for_column(
    console: Console,
    session: _BoardSession,
    target_column: _BoardColumn,
) -> tuple[str | None, str | None]:
    """Resolve target state for a destination column."""
    if target_column.title == "NOT STARTED":
        return None, None

    if session.args.coalesce_completed and target_column.title == "COMPLETED":
        done_state = _choose_done_state(console, session.done_states)
        if done_state is None:
            return None, "State move cancelled"
        return done_state, None

    return target_column.title, None


def _max_column_nodes(columns: list[_BoardColumn]) -> int:
    """Return maximum node count among board columns."""
    return max((len(column.nodes) for column in columns), default=0)


def _ensure_selection_bounds(session: _BoardSession) -> None:
    """Clamp current selection to available columns and rows."""
    if not session.columns:
        session.selected_column_index = 0
        session.selected_row_index = 0
        return

    session.selected_column_index = min(
        max(session.selected_column_index, 0),
        len(session.columns) - 1,
    )
    selected_nodes = session.columns[session.selected_column_index].nodes
    if not selected_nodes:
        session.selected_row_index = 0
        return
    session.selected_row_index = min(max(session.selected_row_index, 0), len(selected_nodes) - 1)


def _selected_node(session: _BoardSession) -> Heading | None:
    """Return selected task node, if current selection targets one."""
    if not session.columns:
        return None
    selected_nodes = session.columns[session.selected_column_index].nodes
    if not selected_nodes:
        return None
    if session.selected_row_index < 0 or session.selected_row_index >= len(selected_nodes):
        return None
    return selected_nodes[session.selected_row_index]


def _reload_session(
    session: _BoardSession,
    preserve_identity: _BoardHeadingIdentity | None,
) -> None:
    """Reload processed nodes and rebuild board columns."""
    nodes, discovered_todo_states, discovered_done_states = load_and_process_data(session.args)
    todo_states, done_states = _resolved_states(
        session.args,
        discovered_todo_states,
        discovered_done_states,
    )

    session.nodes = nodes
    session.todo_states = todo_states
    session.done_states = done_states
    session.columns = _build_flow_board_columns(
        nodes,
        todo_states,
        done_states,
        session.args.coalesce_completed,
    )

    if preserve_identity is not None:
        for column_index, column in enumerate(session.columns):
            for row_index, node in enumerate(column.nodes):
                if heading_identity_matches(node, preserve_identity):
                    session.selected_column_index = column_index
                    session.selected_row_index = row_index
                    _ensure_selection_bounds(session)
                    return

    _ensure_selection_bounds(session)


def _create_flow_board_session(
    args: BoardArgs,
    nodes: list[Heading],
    todo_states: list[str],
    done_states: list[str],
    color_enabled: bool,
) -> _BoardSession:
    """Create interactive flow board session state."""
    columns = _build_flow_board_columns(nodes, todo_states, done_states, args.coalesce_completed)
    selected_column_index = 0
    for index, column in enumerate(columns):
        if column.nodes:
            selected_column_index = index
            break

    session = _BoardSession(
        args=args,
        nodes=nodes,
        todo_states=todo_states,
        done_states=done_states,
        columns=columns,
        color_enabled=color_enabled,
        selected_column_index=selected_column_index,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
    )
    _ensure_selection_bounds(session)
    return session


def _move_selection_vertical(session: _BoardSession, step: int) -> None:
    """Move highlighted task up/down in the selected column."""
    selected_nodes = session.columns[session.selected_column_index].nodes
    if not selected_nodes:
        session.status_message = "Selected column has no tasks"
        return

    next_index = session.selected_row_index + step
    session.selected_row_index = min(max(next_index, 0), len(selected_nodes) - 1)


def _move_selection_horizontal(session: _BoardSession, step: int) -> None:
    """Move highlighted lane left/right, skipping empty columns."""
    next_column = session.selected_column_index + step
    while 0 <= next_column < len(session.columns):
        selected_nodes = session.columns[next_column].nodes
        if selected_nodes:
            session.selected_column_index = next_column
            session.selected_row_index = min(session.selected_row_index, len(selected_nodes) - 1)
            return
        next_column += step


def _apply_state_move(console: Console, session: _BoardSession, *, direction: int) -> None:
    """Move selected task to neighboring column by changing TODO state."""
    heading = _selected_node(session)
    if heading is None:
        session.status_message = "Action available only on task panels"
        return

    target_column_index = session.selected_column_index + direction
    if target_column_index < 0 or target_column_index >= len(session.columns):
        session.status_message = "No neighboring column in that direction"
        return

    target_column = session.columns[target_column_index]
    new_state, status = _choose_target_state_for_column(console, session, target_column)
    if status is not None:
        session.status_message = status
        return

    old_state = heading.todo
    if old_state == new_state:
        session.status_message = "State unchanged"
        return

    action_now = local_now()
    heading.todo = new_state
    append_repeat_transition(heading, old_state, new_state, action_now)

    if heading.scheduled is not None and _advance_timestamp_by_repeater(heading.scheduled):
        logger.info(
            "Flow board repeater advance: file=%s title=%s id=%s field=scheduled value=%s",
            heading.document.filename,
            heading.title_text,
            heading.id,
            heading.scheduled,
        )
    if heading.deadline is not None and _advance_timestamp_by_repeater(heading.deadline):
        logger.info(
            "Flow board repeater advance: file=%s title=%s id=%s field=deadline value=%s",
            heading.document.filename,
            heading.title_text,
            heading.id,
            heading.deadline,
        )

    logger.info(
        "Flow board set state: file=%s title=%s id=%s from=%s to=%s",
        heading.document.filename,
        heading.title_text,
        heading.id,
        old_state,
        new_state,
    )

    _save_document_changes(heading.document)
    preserve_identity = heading_identity(heading)
    _reload_session(session, preserve_identity)
    session.status_message = f"State updated: {old_state or '-'} -> {new_state or '-'}"


def _apply_priority_shift(session: _BoardSession, *, increase: bool) -> None:
    """Increase or decrease selected task priority."""
    heading = _selected_node(session)
    if heading is None:
        session.status_message = "Action available only on task panels"
        return

    old_priority = heading.priority
    new_priority = shift_priority(old_priority, increase=increase)
    if old_priority == new_priority:
        session.status_message = "Priority unchanged"
        return

    heading.priority = new_priority
    logger.info(
        "Flow board set priority: file=%s title=%s id=%s from=%s to=%s",
        heading.document.filename,
        heading.title_text,
        heading.id,
        old_priority,
        new_priority,
    )
    _save_document_changes(heading.document)
    preserve_identity = heading_identity(heading)
    _reload_session(session, preserve_identity)
    session.status_message = f"Priority updated: {old_priority or '-'} -> {new_priority or '-'}"


def _open_selected_task_detail(console: Console, session: _BoardSession) -> None:
    """Open selected task detail in pager for scrolling and selection."""
    heading = _selected_node(session)
    if heading is None:
        session.status_message = "Action available only on task panels"
        return

    session.status_message = ""
    set_mouse_reporting(False)
    try:
        open_task_detail_in_pager(console, heading, color_enabled=session.color_enabled)
    finally:
        set_mouse_reporting(True)


def _interactive_viewport_rows(console_height: int) -> int:
    """Return number of visible task rows in interactive mode."""
    available_space = console_height - _INTERACTIVE_HEADER_HEIGHT - _INTERACTIVE_FOOTER_HEIGHT
    available_lines = max(1, available_space)
    return max(1, available_lines // _INTERACTIVE_PANEL_HEIGHT)


def _interactive_row_heights(
    session: _BoardSession,
    render: _BoardPanelRenderConfig,
) -> list[int]:
    """Estimate rendered interactive row heights across all columns."""
    total_rows = _max_column_nodes(session.columns)
    row_heights: list[int] = []
    for row_index in range(total_rows):
        max_height = 1
        for column in session.columns:
            if row_index >= len(column.nodes):
                continue
            max_height = max(max_height, _interactive_panel_height(column.nodes[row_index], render))
        row_heights.append(max_height)
    return row_heights


def _window_end_for_height(
    row_heights: list[int],
    start_row: int,
    available_lines: int,
) -> tuple[int, int]:
    """Return visible row-window end index and used line count."""
    if not row_heights:
        return 0, 0

    start = min(max(start_row, 0), len(row_heights) - 1)
    used_lines = 0
    end = start
    while end < len(row_heights):
        next_height = row_heights[end]
        if end > start and used_lines + next_height > available_lines:
            break
        used_lines += next_height
        end += 1
        if used_lines >= available_lines:
            break
    return end, used_lines


def _sync_scroll_for_selection(
    session: _BoardSession,
    row_heights: list[int],
    available_lines: int,
) -> tuple[int, int, int]:
    """Keep highlighted row in view and return visible row window bounds."""
    if not row_heights:
        session.scroll_offset = 0
        return 0, 0, 0

    max_offset = max(0, len(row_heights) - 1)
    session.scroll_offset = min(max(session.scroll_offset, 0), max_offset)

    selected_nodes = session.columns[session.selected_column_index].nodes
    if not selected_nodes:
        end_row, used_lines = _window_end_for_height(
            row_heights,
            session.scroll_offset,
            available_lines,
        )
        return session.scroll_offset, end_row, used_lines

    selected_row = session.selected_row_index
    session.scroll_offset = min(session.scroll_offset, selected_row)

    end_row, used_lines = _window_end_for_height(
        row_heights,
        session.scroll_offset,
        available_lines,
    )
    while selected_row >= end_row and session.scroll_offset < selected_row:
        session.scroll_offset += 1
        end_row, used_lines = _window_end_for_height(
            row_heights,
            session.scroll_offset,
            available_lines,
        )

    return session.scroll_offset, end_row, used_lines


def _interactive_flow_board_renderable(console: Console, session: _BoardSession) -> Group:
    """Build scrollable interactive flow board with fixed headers/footer."""
    panel_content_width = _estimate_panel_content_width(console.width, len(session.columns))
    available_lines = max(
        1,
        console.size.height - _INTERACTIVE_HEADER_HEIGHT - _INTERACTIVE_FOOTER_HEIGHT,
    )

    header = Table(expand=True, box=None, show_lines=False, show_header=False, pad_edge=False)
    for _ in session.columns:
        header.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
    header_cells: list[Text] = []
    for column in session.columns:
        state = _resolve_header_state(column, session.done_states, session.args.coalesce_completed)
        title_markup = _column_title_markup(
            column.title,
            state,
            session.done_states,
            session.todo_states,
            session.color_enabled,
        )
        title_text = Text.from_markup(title_markup)
        title_text.overflow = "ellipsis"
        title_text.no_wrap = True
        header_cells.append(
            title_text,
        )
    header.add_row(*header_cells)

    body = Table(expand=True, box=None, show_lines=False, show_header=False, pad_edge=False)
    for _ in session.columns:
        body.add_column(ratio=1)

    render = _BoardPanelRenderConfig(
        width=panel_content_width,
        color_enabled=session.color_enabled,
        done_states=session.done_states,
        todo_states=session.todo_states,
        coalesce_completed=session.args.coalesce_completed,
    )

    row_heights = _interactive_row_heights(session, render)
    start_row, end_row, used_lines = _sync_scroll_for_selection(
        session,
        row_heights,
        available_lines,
    )
    filler_lines = max(0, available_lines - used_lines)

    for row_index in range(start_row, end_row):
        cells: list[RenderableType] = []
        for column_index, column in enumerate(session.columns):
            if row_index >= len(column.nodes):
                cells.append(Text(""))
                continue

            node = column.nodes[row_index]
            highlighted = (
                column_index == session.selected_column_index
                and row_index == session.selected_row_index
            )
            cells.append(_build_task_panel(node, render, highlighted=highlighted))
        body.add_row(*cells)

    controls = (
        "Up/Down, Left/Right, Wheel move"
        " | Enter view"
        " | Shift+Left/Right state"
        " | Shift+Up/Down priority"
        " | q/Esc quit"
    )
    total_rows = max(_max_column_nodes(session.columns), 1)
    visible_end_row = min(end_row, total_rows)
    row_text = f"Rows {visible_end_row}/{total_rows}"
    status = session.status_message or ""
    footer_style = "dim" if session.color_enabled else ""

    footer_line = Table.grid(expand=True)
    footer_line.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
    footer_line.add_column(ratio=4, justify="right", no_wrap=True, overflow="ellipsis")
    footer_line.add_row(
        Text(row_text, style=footer_style, no_wrap=True, overflow="ellipsis"),
        Text(controls, style=footer_style, no_wrap=True, overflow="ellipsis"),
    )

    filler = Table.grid(expand=True)
    filler.add_column(ratio=1)
    for _ in range(filler_lines):
        filler.add_row(Text(""))

    return Group(
        header,
        Rule(style=footer_style),
        body,
        filler,
        Rule(style=footer_style),
        footer_line,
        Text(status, style=footer_style, no_wrap=True, overflow="ellipsis"),
    )


def _flow_board_key_bindings(
    console: Console,
    session: _BoardSession,
) -> dict[str, KeyBinding]:
    """Build interactive key bindings for flow board session."""
    return {
        "q": KeyBinding(lambda: False),
        "ESC": KeyBinding(lambda: False),
        "DOWN": key_binding_for_action(lambda: _move_selection_vertical(session, 1)),
        "WHEEL-DOWN": key_binding_for_action(lambda: _move_selection_vertical(session, 1)),
        "UP": key_binding_for_action(lambda: _move_selection_vertical(session, -1)),
        "WHEEL-UP": key_binding_for_action(lambda: _move_selection_vertical(session, -1)),
        "RIGHT": key_binding_for_action(lambda: _move_selection_horizontal(session, 1)),
        "LEFT": key_binding_for_action(lambda: _move_selection_horizontal(session, -1)),
        "ENTER": key_binding_for_action(
            lambda: _open_selected_task_detail(console, session),
            requires_live_pause=True,
        ),
        "S-LEFT": key_binding_for_action(
            lambda: _apply_state_move(console, session, direction=-1),
            requires_live_pause=True,
        ),
        "S-RIGHT": key_binding_for_action(
            lambda: _apply_state_move(console, session, direction=1),
            requires_live_pause=True,
        ),
        "S-UP": key_binding_for_action(lambda: _apply_priority_shift(session, increase=True)),
        "S-DOWN": key_binding_for_action(lambda: _apply_priority_shift(session, increase=False)),
    }


def _handle_interactive_key(console: Console, session: _BoardSession, key: str) -> bool:
    """Handle one interactive keypress and return whether to continue."""
    result = dispatch_key_binding(key, _flow_board_key_bindings(console, session))
    if result.handled:
        return result.continue_loop

    if key:
        session.status_message = f"Unsupported key: {key}"
    return True


def _run_flow_board_interactive(console: Console, session: _BoardSession) -> None:
    """Run interactive flow board event loop."""
    set_mouse_reporting(True)
    try:
        with Live(
            _interactive_flow_board_renderable(console, session),
            console=console,
            screen=True,
            refresh_per_second=12,
            auto_refresh=False,
        ) as live:
            while True:
                key = read_keypress(timeout_seconds=0.2)
                if not key:
                    live.update(_interactive_flow_board_renderable(console, session), refresh=True)
                    continue

                if key_binding_requires_live_pause(key, _flow_board_key_bindings(console, session)):
                    live.stop()
                    should_continue = _handle_interactive_key(console, session, key)
                    live.start()
                else:
                    should_continue = _handle_interactive_key(console, session, key)

                if not should_continue:
                    break
                live.update(_interactive_flow_board_renderable(console, session), refresh=True)
    finally:
        set_mouse_reporting(False)


def run_flow_board(args: BoardArgs) -> None:
    """Run the flow board command."""
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
        nodes, discovered_todo_states, discovered_done_states = load_and_process_data(args)
        todo_states, done_states = _resolved_states(
            args,
            discovered_todo_states,
            discovered_done_states,
        )

    if not nodes:
        console.print("No results", markup=False)
        return

    if sys.stdin.isatty() and sys.stdout.isatty():
        _run_flow_board_interactive(
            console,
            _create_flow_board_session(
                args,
                nodes,
                todo_states,
                done_states,
                color_enabled,
            ),
        )
        return

    columns = _build_flow_board_columns(nodes, todo_states, done_states, args.coalesce_completed)
    _render_static_flow_board(
        console,
        columns,
        _BoardStaticRenderInput(
            done_states=done_states,
            todo_states=todo_states,
            color_enabled=color_enabled,
            coalesce_completed=args.coalesce_completed,
        ),
    )


def register(app: typer.Typer) -> None:
    """Register the flow board command."""

    @app.command(
        "board",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )
    def flow_board(  # noqa: PLR0913
        files: list[str] | None = typer.Argument(  # noqa: B008
            None,
            metavar="FILE",
            help="Org-mode archive files or directories to analyze",
        ),
        config: str = typer.Option(
            ".org-cli.yaml",
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
        """Display tasks as an interactive flow board."""
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
        config_module.log_applied_config_defaults(args, sys.argv[1:], "board")
        config_module.log_command_arguments(args, "board")
        run_flow_board(args)
