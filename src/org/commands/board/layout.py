"""Board interactive and static layout helpers."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Protocol

from rich import box
from rich.align import Align
from rich.cells import cell_len
from rich.console import Console, Group, RenderableType
from rich.errors import MarkupError
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from org.color import get_state_color
from org.commands.interactive_common import InteractiveHelpEntry
from org.tui import heading_title_to_text, task_priority_to_text, task_tags_to_text


if TYPE_CHECKING:
    from collections.abc import Sequence

    from org_parser.document import Heading

    from .events import BoardSession


class _BoardColumnLike(Protocol):
    @property
    def title(self) -> str: ...

    @property
    def nodes(self) -> list[Heading]: ...


_HIGHLIGHT_PANEL_STYLE = "on grey23"
_INTERACTIVE_PANEL_HEIGHT = 4


BOARD_HELP_ENTRIES = [
    InteractiveHelpEntry("Esc/q", "Exit the board and return to the shell."),
    InteractiveHelpEntry(
        "Up/Down, Wheel",
        "Move the highlighted task up or down within the selected column.",
    ),
    InteractiveHelpEntry(
        "Left/Right",
        "Move focus across columns without changing task data.",
    ),
    InteractiveHelpEntry(
        "Enter",
        "Open the selected task subtree in the external editor workflow.",
    ),
    InteractiveHelpEntry(
        "a",
        "Capture a new task from configured templates and reload the board.",
    ),
    InteractiveHelpEntry(
        "$",
        "Archive the selected task subtree using standard archive rules.",
    ),
    InteractiveHelpEntry(
        "/",
        "Open search prompt and filter visible tasks in every column.",
    ),
    InteractiveHelpEntry(
        "x",
        "Clear active search filter and restore full board.",
    ),
    InteractiveHelpEntry(
        "S-Left/S-Right",
        "Step TODO state backward or forward using document state order.",
    ),
    InteractiveHelpEntry(
        "S-Up/S-Down",
        "Increase or decrease priority across A/B/C/none.",
    ),
]


def _max_column_nodes(columns: Sequence[_BoardColumnLike]) -> int:
    """Return maximum node count among board columns."""
    return max((len(column.nodes) for column in columns), default=0)


class BoardPanelRenderConfig:
    """Rendering context passed to task panel builders."""

    def __init__(
        self,
        *,
        width: int,
        color_enabled: bool,
        done_states: list[str],
        todo_states: list[str],
    ) -> None:
        """Store board panel rendering settings."""
        self.width = width
        self.color_enabled = color_enabled
        self.done_states = done_states
        self.todo_states = todo_states


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


def _state_prefix(
    state: str | None,
    done_states: list[str],
    todo_states: list[str],
    color_enabled: bool,
) -> Text:
    """Build a styled state prefix for task heading text."""
    if state is None:
        return Text("")
    style = get_state_color(state, done_states, todo_states, color_enabled)
    prefix = Text("")
    prefix.append(state, style=style or "")
    prefix.append(" ")
    return prefix


def build_task_panel(
    node: Heading,
    render: BoardPanelRenderConfig,
    *,
    highlighted: bool,
) -> Panel:
    """Build a visual panel for one task."""
    content = Text("")
    content.append_text(
        _state_prefix(
            node.todo,
            render.done_states,
            render.todo_states,
            render.color_enabled,
        ),
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


def _heading_and_meta_lines(node: Heading, render: BoardPanelRenderConfig) -> tuple[int, int]:
    """Estimate wrapped line counts for panel heading and metadata."""
    heading = Text("")
    heading.append_text(
        _state_prefix(
            node.todo,
            render.done_states,
            render.todo_states,
            color_enabled=False,
        ),
    )
    heading.append_text(heading_title_to_text(node))
    heading_lines = max(1, math.ceil(cell_len(heading.plain) / max(1, render.width)))

    metadata = _task_metadata_text(node, color_enabled=False)
    metadata_lines = 0
    if metadata.plain:
        metadata_lines = max(1, math.ceil(cell_len(metadata.plain) / max(1, render.width)))

    return heading_lines, metadata_lines


def _interactive_panel_height(node: Heading, render: BoardPanelRenderConfig) -> int:
    """Estimate interactive panel height for one node."""
    heading_lines, metadata_lines = _heading_and_meta_lines(node, render)
    return heading_lines + metadata_lines + 2


def render_column_title_text(title: str) -> Text:
    """Render column title as Rich markup with literal fallback."""
    try:
        return Text.from_markup(title)
    except MarkupError:
        return Text(title)


def estimate_panel_content_width(console_width: int, column_count: int) -> int:
    """Estimate panel inner width for pre-wrapping task card lines."""
    safe_columns = max(1, column_count)
    raw_width = console_width // safe_columns
    return max(10, raw_width - 8)


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


def _estimate_board_height(columns: Sequence[_BoardColumnLike], panel_content_width: int) -> int:
    """Estimate total rendered board table height in terminal lines."""
    column_heights = [
        _column_content_height(column.nodes, panel_content_width) for column in columns
    ]
    content_row_height = max(column_heights, default=1)
    return content_row_height + 3


def render_static_flow_board(
    console: Console,
    columns: Sequence[_BoardColumnLike],
    *,
    done_states: list[str],
    todo_states: list[str],
    color_enabled: bool,
) -> None:
    """Render non-interactive flow board output."""
    table = Table(expand=True, box=box.SQUARE, show_lines=False, show_header=False)
    for _ in columns:
        table.add_column(ratio=1)

    header_row = [Align.center(render_column_title_text(column.title)) for column in columns]
    table.add_row(*header_row)

    panel_content_width = estimate_panel_content_width(console.width, len(columns))
    render = BoardPanelRenderConfig(
        width=panel_content_width,
        color_enabled=color_enabled,
        done_states=done_states,
        todo_states=todo_states,
    )
    content_cells: list[RenderableType] = []
    for column in columns:
        if not column.nodes:
            content_cells.append(Text(""))
            continue
        panels = [build_task_panel(node, render, highlighted=False) for node in column.nodes]
        content_cells.append(Group(*panels))
    table.add_row(*content_cells)

    board_height = _estimate_board_height(columns, panel_content_width)
    if board_height > console.height:
        with console.pager(styles=color_enabled):
            console.print(table)
        return

    console.print(table)


def _column_row_heights(nodes: Sequence[Heading], render: BoardPanelRenderConfig) -> list[int]:
    return [_interactive_panel_height(node, render) for node in nodes]


def _selected_column_row_heights(
    session: BoardSession,
    render: BoardPanelRenderConfig,
) -> list[int]:
    if not session.columns:
        return []
    selected_nodes = session.columns[session.selected_column_index].nodes
    return _column_row_heights(selected_nodes, render)


def _window_end_for_height(
    row_heights: list[int],
    start_row: int,
    available_lines: int,
) -> tuple[int, int]:
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


def sync_scroll_for_selection(
    session: BoardSession,
    row_heights: list[int],
    available_lines: int,
) -> tuple[int, int, int]:
    """Clamp scroll offset and return the selected-column visible row window."""
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


def selected_column_window(
    session: BoardSession,
    render: BoardPanelRenderConfig,
    *,
    body_height: int,
) -> tuple[int, int]:
    """Return the selected-column visible row window after syncing scroll state."""
    selected_row_heights = _selected_column_row_heights(session, render)
    start_row, end_row, _used_lines = sync_scroll_for_selection(
        session,
        selected_row_heights,
        body_height,
    )
    return start_row, end_row


def column_window_end(
    nodes: Sequence[Heading],
    render: BoardPanelRenderConfig,
    *,
    start_row: int,
    body_height: int,
) -> int:
    """Return the exclusive end row for one board column's visible card slice."""
    column_end_row, _used_lines = _window_end_for_height(
        _column_row_heights(nodes, render),
        start_row,
        body_height,
    )
    if column_end_row < len(nodes):
        column_end_row += 1
    return column_end_row


def selected_column_total_rows(session: BoardSession) -> int:
    """Return the selected column row count, defaulting to one for footer display."""
    if not session.columns:
        return 1
    return max(len(session.columns[session.selected_column_index].nodes), 1)
