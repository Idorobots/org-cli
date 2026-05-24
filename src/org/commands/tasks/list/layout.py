"""Tasks list interactive and static layout helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console, Group
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from org.commands.interactive_common import (
    INTERACTIVE_HELP_FOOTER_HINT,
    build_footer_prompt_text,
    render_interactive_help_modal,
)
from org.tui import TaskLineConfig, format_task_line

from .events import _TASKS_LIST_HELP_ENTRIES, _ensure_selection_bounds, _TasksListSession


if TYPE_CHECKING:
    from org_parser.document import Heading


_HIGHLIGHT_ROW_STYLE = "on grey23"


def _build_task_row_text(
    node: Heading,
    session: _TasksListSession,
    *,
    line_width: int,
) -> Text:
    """Build one interactive row using the static task line format."""
    line = format_task_line(
        node,
        TaskLineConfig(
            color_enabled=session.color_enabled,
            done_states=session.done_states,
            todo_states=session.todo_states,
            line_width=line_width,
        ),
    )
    if session.color_enabled:
        return Text.from_markup(line)
    return Text(line)


def _sync_scroll(session: _TasksListSession, viewport_height: int) -> None:
    """Keep selected row inside the current viewport window."""
    max_offset = max(0, len(session.visible_nodes) - viewport_height)
    session.scroll_offset = min(max(session.scroll_offset, 0), max_offset)

    if not session.visible_nodes:
        return

    if session.selected_index < session.scroll_offset:
        session.scroll_offset = session.selected_index
    elif session.selected_index >= session.scroll_offset + viewport_height:
        session.scroll_offset = session.selected_index - viewport_height + 1

    session.scroll_offset = min(max(session.scroll_offset, 0), max_offset)


def _interactive_tasks_list_renderable(console: Console, session: _TasksListSession) -> Group:
    """Build scrollable interactive tasks list renderable."""
    if session.show_help_modal:
        return Group(
            render_interactive_help_modal(
                _TASKS_LIST_HELP_ENTRIES,
                color_enabled=session.color_enabled,
            ),
        )

    viewport_height = max(5, console.size.height - 3)
    _ensure_selection_bounds(session)
    _sync_scroll(session, viewport_height)

    window = session.visible_nodes[session.scroll_offset : session.scroll_offset + viewport_height]
    viewport_table = Table.grid(expand=True)
    viewport_table.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
    for index, node in enumerate(window, start=session.scroll_offset):
        row_style = _HIGHLIGHT_ROW_STYLE if index == session.selected_index else ""
        viewport_table.add_row(
            _build_task_row_text(node, session, line_width=console.size.width),
            style=row_style,
        )

    for _ in range(viewport_height - len(window)):
        viewport_table.add_row(Text(""))

    selected_row = session.selected_index + 1 if session.visible_nodes else 0
    total_rows = len(session.visible_nodes)
    search_text = session.search_text or "-"
    row_text = f"Rows {selected_row}/{total_rows} | Search: {search_text}"
    prompt_line = None
    active_prompt = session.active_prompt
    if active_prompt is not None:
        prompt_line = build_footer_prompt_text(active_prompt.prompt)
    status = session.status_message or ""
    footer_style = "dim" if session.color_enabled else ""

    footer_line = Table.grid(expand=True)
    footer_line.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
    footer_line.add_column(ratio=4, justify="right", no_wrap=True, overflow="ellipsis")
    footer_line.add_row(
        Text(row_text, style=footer_style, no_wrap=True, overflow="ellipsis"),
        Text(
            INTERACTIVE_HELP_FOOTER_HINT,
            style=footer_style,
            no_wrap=True,
            overflow="ellipsis",
        ),
    )

    status_text = Text(status, style=footer_style, no_wrap=True, overflow="ellipsis")
    if prompt_line is None:
        return Group(viewport_table, Rule(style=footer_style), footer_line, status_text)
    return Group(viewport_table, Rule(style=footer_style), footer_line, prompt_line, status_text)


interactive_tasks_list_renderable = _interactive_tasks_list_renderable
build_task_row_text = _build_task_row_text


__all__ = [
    "_interactive_tasks_list_renderable",
    "build_task_row_text",
    "interactive_tasks_list_renderable",
]
