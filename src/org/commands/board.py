"""Board command."""

from __future__ import annotations

import logging
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, cast

import typer
from rich import box
from rich.cells import cell_len
from rich.console import Group, RenderableType
from rich.errors import MarkupError
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from org import config as config_module
from org.cli_common import load_and_process_data
from org.color import get_state_color
from org.commands.archive import archive_heading_subtree_and_save
from org.commands.editor import edit_heading_subtree_in_external_editor
from org.commands.interactive_action_builders import (
    can_activate_configured_capture_templates,
    quit_view_action,
    status_external_action,
    status_noninteractive_action,
    status_view_action,
    view_action,
)
from org.commands.interactive_actions import (
    ActionResult,
    PromptInteractiveAction,
    PromptInteractiveActionContract,
    SessionAction,
    action_requires_live_pause,
    dispatch_action_key,
    handle_active_interactive_action_input,
)
from org.commands.interactive_common import (
    INTERACTIVE_HELP_FOOTER_HINT,
    FooterPromptState,
    HeadingIdentity,
    InteractiveHelpEntry,
    advance_timestamp_by_repeater,
    append_repeat_transition,
    apply_help_modal_key,
    build_footer_prompt_text,
    heading_identity,
    heading_identity_matches,
    interactive_help_command_text,
    local_now,
    read_keypress,
    render_interactive_help_modal,
    set_mouse_reporting,
    shift_priority,
)
from org.commands.search_common import filter_nodes_by_search
from org.commands.tasks.capture import TasksCaptureArgs, capture_task
from org.commands.tasks.common import (
    PromptActionConfig,
    capture_template_prompt_config,
    configured_capture_template_names,
    resolve_capture_template_selection,
    save_document,
)
from org.query_language import (
    CompiledQuery,
    EvalContext,
    QueryParseError,
    QueryRuntimeError,
    Stream,
    compile_query_text,
)
from org.tui import (
    build_console,
    heading_title_to_text,
    processing_status,
    setup_output,
    task_priority_to_text,
    task_tags_to_text,
)


if TYPE_CHECKING:
    from org_parser.document import Document, Heading
    from rich.console import Console


logger = logging.getLogger("org")
_HIGHLIGHT_PANEL_STYLE = "on grey23"
_INTERACTIVE_HEADER_HEIGHT = 2
_INTERACTIVE_FOOTER_HEIGHT = 3
_INTERACTIVE_FOOTER_HEIGHT_WITH_PROMPT = 4
_INTERACTIVE_PANEL_HEIGHT = 4
_INTERACTIVE_INPUT_TIMEOUT_SECONDS = 0.05


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
    view: str | None
    width: int | None
    max_results: int | None
    offset: int
    days: int
    order_by_level: bool
    order_by_file_order: bool
    order_by_file_order_reversed: bool
    order_by_priority: bool
    order_by_timestamp_asc: bool
    order_by_timestamp_desc: bool
    with_tags_as_category: bool


@dataclass(frozen=True)
class _BoardColumn:
    """One board column with title and assigned tasks."""

    title: str
    nodes: list[Heading]


@dataclass(frozen=True)
class _BoardColumnSpec:
    """One board column filter specification."""

    name: str
    view_name: str
    query: CompiledQuery


@dataclass(frozen=True)
class _BoardPanelRenderConfig:
    """Rendering context passed to task panel builders."""

    width: int
    color_enabled: bool
    done_states: list[str]
    todo_states: list[str]


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
    all_columns: list[_BoardColumn] = field(default_factory=list)
    search_text: str = ""
    search_prompt_previous_text: str | None = None
    show_help_modal: bool = False
    active_interactive_action: PromptInteractiveActionContract[_BoardSession] | None = None


@dataclass(frozen=True)
class _BoardStaticRenderInput:
    """Rendering input for non-interactive board output."""

    done_states: list[str]
    todo_states: list[str]
    color_enabled: bool


_BoardHeadingIdentity = HeadingIdentity


_BOARD_HELP_ENTRIES = [
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


def _priority_rank(priority: str | None) -> int:
    """Return sort rank for board priority ordering."""
    rank = {"A": 0, "B": 1, "C": 2}
    return rank.get(priority or "", 3)


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


def _build_task_panel(
    node: Heading,
    render: _BoardPanelRenderConfig,
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


def _heading_and_meta_lines(node: Heading, render: _BoardPanelRenderConfig) -> tuple[int, int]:
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


def _interactive_panel_height(node: Heading, render: _BoardPanelRenderConfig) -> int:
    """Estimate interactive panel height for one node."""
    heading_lines, metadata_lines = _heading_and_meta_lines(node, render)
    return heading_lines + metadata_lines + 2


def _render_column_title_text(title: str) -> Text:
    """Render column title as Rich markup with literal fallback."""
    try:
        return Text.from_markup(title)
    except MarkupError:
        return Text(title)


def _compile_column_filter_query(
    filter_query: str,
    order_by: str | None,
) -> CompiledQuery:
    """Compile one board column filter/order query text."""
    base_query = f"select({filter_query})"
    if order_by is None:
        return compile_query_text(base_query)
    return compile_query_text(f"{base_query} | sort_by({order_by})")


def _fallback_view_config() -> config_module.BoardViewConfig:
    """Return built-in fallback board filter view definition."""
    return config_module.BoardViewConfig(
        name="fallback",
        columns=[
            config_module.BoardColumnConfig(name="Backlog", filter=".todo == null"),
            config_module.BoardColumnConfig(
                name="TODO",
                filter=".todo != null and not(.is_completed)",
            ),
            config_module.BoardColumnConfig(name="DONE", filter=".is_completed"),
        ],
    )


def _compile_view_column_specs(view: config_module.BoardViewConfig) -> list[_BoardColumnSpec]:
    """Compile one board view's filters into renderable column specs."""
    column_specs: list[_BoardColumnSpec] = []
    for column in view.columns:
        try:
            query = _compile_column_filter_query(column.filter, column.order_by)
        except QueryParseError as err:
            raise typer.BadParameter(
                f"Invalid board filter/order-by (view={view.name}, column={column.name}): {err}",
            ) from err
        column_specs.append(
            _BoardColumnSpec(
                name=column.name,
                view_name=view.name,
                query=query,
            ),
        )
    return column_specs


def _resolve_selected_view_name(args: BoardArgs) -> str | None:
    """Resolve selected board view name from command args."""
    if args.view is None:
        return None

    selected_view = args.view.strip()
    if not selected_view:
        return None
    return selected_view


def _resolve_column_specs(args: BoardArgs) -> list[_BoardColumnSpec]:
    """Resolve configured or fallback filter columns for board rendering."""
    selected_view = _resolve_selected_view_name(args)
    configured_views = config_module.CONFIG_BOARD_VIEWS

    if selected_view is None:
        return _compile_view_column_specs(_fallback_view_config())

    if not configured_views:
        raise typer.BadParameter("--view requested, but no board views are configured")

    selected_view_config = configured_views.get(selected_view)
    if selected_view_config is None:
        raise typer.BadParameter(f"Requested board view not found: {selected_view}")

    return _compile_view_column_specs(selected_view_config)


def _build_selector_board_columns(
    nodes: list[Heading],
    column_specs: list[_BoardColumnSpec],
) -> list[_BoardColumn]:
    """Evaluate filter specs against processed task stream."""
    columns: list[_BoardColumn] = []
    for spec in column_specs:
        try:
            results = spec.query(Stream(nodes), EvalContext({}))
        except QueryRuntimeError as err:
            raise typer.BadParameter(
                (
                    "Board filter/order-by query failed "
                    f"(view={spec.view_name}, column={spec.name}): {err}"
                ),
            ) from err

        column_nodes = [cast("Heading", result) for result in results]
        columns.append(_BoardColumn(title=spec.name, nodes=column_nodes))

    return columns


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


def _coerce_latest_timestamp_start(node: Heading) -> datetime | None:
    """Return node latest timestamp start value when available."""
    latest_timestamp = node.latest_timestamp
    if latest_timestamp is None:
        return None
    return latest_timestamp.start


def _filter_recent_completed_nodes(nodes: list[Heading], days: int) -> list[Heading]:
    """Keep completed tasks only when latest_timestamp is within days window."""
    now = local_now()
    cutoff = now - timedelta(days=days)

    filtered: list[Heading] = []
    for node in nodes:
        if not node.is_completed:
            filtered.append(node)
            continue

        latest_start = _coerce_latest_timestamp_start(node)
        if latest_start is None:
            continue
        if latest_start.tzinfo is None:
            latest_start = latest_start.replace(tzinfo=now.tzinfo)
        if latest_start >= cutoff:
            filtered.append(node)

    return filtered


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

    header_row = [_render_column_title_text(column.title) for column in columns]
    table.add_row(*header_row)

    panel_content_width = _estimate_panel_content_width(console.width, len(columns))
    render = _BoardPanelRenderConfig(
        width=panel_content_width,
        color_enabled=render_input.color_enabled,
        done_states=render_input.done_states,
        todo_states=render_input.todo_states,
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
    save_document(document)


def _step_heading_state(heading: Heading, *, direction: int) -> tuple[str | None, str | None]:
    """Resolve next heading state from document all_states ordering."""
    ordered_states = list(dict.fromkeys(heading.document.all_states))
    if not ordered_states:
        return heading.todo, "No TODO states configured in document"

    current_state = heading.todo
    current_index = ordered_states.index(current_state) if current_state in ordered_states else -1

    new_state = current_state
    status: str | None = None
    if current_index == -1:
        if direction > 0:
            new_state = ordered_states[0]
        elif current_state is None:
            status = "State unchanged"
        else:
            new_state = None
    else:
        step = 1 if direction > 0 else -1
        next_index = current_index + step
        if next_index < 0:
            new_state = None
        elif next_index >= len(ordered_states):
            status = "Already at last state"
        else:
            new_state = ordered_states[next_index]
    return new_state, status


def _max_column_nodes(columns: list[_BoardColumn]) -> int:
    """Return maximum node count among board columns."""
    return max((len(column.nodes) for column in columns), default=0)


def _column_with_filtered_nodes(column: _BoardColumn, search_text: str) -> _BoardColumn:
    """Return one board column with nodes filtered by search text."""
    filtered_nodes = filter_nodes_by_search(column.nodes, search_text)
    return _BoardColumn(title=column.title, nodes=filtered_nodes)


def _filter_columns_by_search(columns: list[_BoardColumn], search_text: str) -> list[_BoardColumn]:
    """Filter nodes in each column by interactive search text."""
    return [_column_with_filtered_nodes(column, search_text) for column in columns]


def _visible_task_count(columns: list[_BoardColumn]) -> int:
    """Return total number of visible tasks across all board columns."""
    return sum(len(column.nodes) for column in columns)


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


def _refresh_visible_columns(
    session: _BoardSession,
    preserve_identity: _BoardHeadingIdentity | None,
) -> None:
    """Refresh visible board columns and restore selected task when possible."""
    source_columns = session.all_columns or session.columns
    session.columns = _filter_columns_by_search(source_columns, session.search_text)

    if preserve_identity is not None:
        for column_index, column in enumerate(session.columns):
            for row_index, node in enumerate(column.nodes):
                if heading_identity_matches(node, preserve_identity):
                    session.selected_column_index = column_index
                    session.selected_row_index = row_index
                    _ensure_selection_bounds(session)
                    return

    _ensure_selection_bounds(session)


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

    filtered_nodes = _filter_recent_completed_nodes(nodes, session.args.days)

    session.nodes = filtered_nodes
    session.todo_states = todo_states
    session.done_states = done_states
    session.all_columns = _build_selector_board_columns(
        filtered_nodes,
        _resolve_column_specs(session.args),
    )
    _refresh_visible_columns(session, preserve_identity)


def _create_flow_board_session(
    args: BoardArgs,
    nodes: list[Heading],
    todo_states: list[str],
    done_states: list[str],
    color_enabled: bool,
) -> _BoardSession:
    """Create interactive flow board session state."""
    columns = _build_selector_board_columns(nodes, _resolve_column_specs(args))
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
        all_columns=columns,
        columns=columns,
        color_enabled=color_enabled,
        selected_column_index=selected_column_index,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
        search_text="",
        show_help_modal=False,
        active_interactive_action=None,
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


def _apply_state_move(session: _BoardSession, *, direction: int) -> None:
    """Step selected task state through document state ordering."""
    heading = _selected_node(session)
    if heading is None:
        session.status_message = "Action available only on task panels"
        return

    new_state, status = _step_heading_state(heading, direction=direction)
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

    if heading.scheduled is not None and advance_timestamp_by_repeater(heading.scheduled):
        logger.info(
            "Flow board repeater advance: file=%s title=%s id=%s field=scheduled value=%s",
            heading.document.filename,
            heading.title_text,
            heading.id,
            heading.scheduled,
        )
    if heading.deadline is not None and advance_timestamp_by_repeater(heading.deadline):
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
    try:
        _reload_session(session, preserve_identity)
    except typer.BadParameter as err:
        session.status_message = str(err)
        return
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
    try:
        _reload_session(session, preserve_identity)
    except typer.BadParameter as err:
        session.status_message = str(err)
        return
    session.status_message = f"Priority updated: {old_priority or '-'} -> {new_priority or '-'}"


def _edit_selected_task_in_external_editor(session: _BoardSession) -> None:
    """Edit selected task subtree in configured external editor."""
    heading = _selected_node(session)
    if heading is None:
        session.status_message = "Action available only on task panels"
        return

    preserve_identity = heading_identity(heading)
    session.status_message = ""
    try:
        edit_result = edit_heading_subtree_in_external_editor(heading)
    except typer.BadParameter as err:
        session.status_message = str(err)
        return

    if not edit_result.changed:
        session.status_message = "No changes."
        return

    try:
        _reload_session(session, preserve_identity)
    except typer.BadParameter as err:
        session.status_message = str(err)
        return
    session.status_message = "Task updated"


def _archive_selected_task(session: _BoardSession) -> None:
    """Archive selected task subtree using shared archive-location rules."""
    heading = _selected_node(session)
    if heading is None:
        session.status_message = "Action available only on task panels"
        return

    session.status_message = ""
    try:
        archive_result = archive_heading_subtree_and_save(heading, {})
    except typer.BadParameter as err:
        session.status_message = str(err)
        return

    preserve_identity = heading_identity(archive_result.heading)
    try:
        _reload_session(session, preserve_identity)
    except typer.BadParameter as err:
        session.status_message = str(err)
        return
    session.status_message = "Task archived"


def _apply_capture_task(session: _BoardSession, template_name: str) -> None:
    """Capture a new task and reload board session."""
    session.status_message = ""
    capture_args = TasksCaptureArgs(
        template_name=template_name,
        config=session.args.config,
        file=None,
        parent=None,
        set_values=None,
    )
    try:
        capture_result = capture_task(capture_args)
    except KeyboardInterrupt:
        session.status_message = "Capture cancelled"
        return
    except typer.BadParameter as err:
        session.status_message = str(err)
        return

    try:
        _reload_session(session, heading_identity(capture_result.heading))
    except typer.BadParameter as err:
        session.status_message = str(err)
        return
    session.status_message = "Task captured"


def _submit_board_capture_action(
    session: _BoardSession,
    _target: _BoardSession,
    raw_value: str,
    options: list[str] | None,
) -> ActionResult:
    """Apply submitted capture template selection from active board prompt."""
    active = session.active_interactive_action
    if active is None:
        return ActionResult(success=False)

    value = raw_value.strip()
    template_name = resolve_capture_template_selection(value, options or [])
    if template_name is None and not value:
        return ActionResult(status_message=active.prompt_config.cancel_status)
    if template_name is None:
        return ActionResult(
            success=False,
            status_message=active.prompt_config.invalid_status,
            keep_prompt_open=True,
        )

    _apply_capture_task(session, template_name)
    return ActionResult(status_message=session.status_message)


def _clear_search(session: _BoardSession) -> None:
    """Clear active interactive search and restore full board columns."""
    if not session.search_text:
        session.status_message = "Search already clear"
        return

    selected = _selected_node(session)
    preserve_identity = heading_identity(selected) if selected is not None else None
    session.search_text = ""
    _refresh_visible_columns(session, preserve_identity)
    session.status_message = "Search cleared"


def _submit_board_search_action(
    session: _BoardSession,
    _target: _BoardSession,
    raw_value: str,
    _options: list[str] | None,
) -> ActionResult:
    """Apply submitted interactive search value."""
    return _apply_search_text(session, raw_value.strip())


def _preview_board_search_action(
    session: _BoardSession,
    _target: _BoardSession,
    raw_value: str,
    _options: list[str] | None,
) -> ActionResult:
    """Live-update board columns while editing interactive search prompt."""
    return _apply_search_text(session, raw_value.strip())


def _cancel_board_search_action(
    session: _BoardSession,
    _target: _BoardSession,
) -> ActionResult:
    """Cancel search prompt and restore previous board search filter."""
    previous_text = session.search_prompt_previous_text or ""
    session.search_prompt_previous_text = None
    _apply_search_text(session, previous_text)
    return ActionResult(status_message="Search cancelled")


def _capture_board_search_prompt_state(session: _BoardSession) -> ActionResult | None:
    """Capture current board search filter before opening search prompt."""
    session.search_prompt_previous_text = session.search_text
    return None


def _apply_search_text(session: _BoardSession, search_text: str) -> ActionResult:
    """Apply search text to board columns and return match status."""
    selected = _selected_node(session)
    preserve_identity = heading_identity(selected) if selected is not None else None
    session.search_text = search_text
    _refresh_visible_columns(session, preserve_identity)
    status = (
        "Search cleared" if not search_text else f"{_visible_task_count(session.columns)} matches"
    )
    return ActionResult(status_message=status)


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


def _column_row_heights(nodes: list[Heading], render: _BoardPanelRenderConfig) -> list[int]:
    """Estimate interactive panel heights for nodes within one column."""
    return [_interactive_panel_height(node, render) for node in nodes]


def _selected_column_row_heights(
    session: _BoardSession,
    render: _BoardPanelRenderConfig,
) -> list[int]:
    """Estimate interactive panel heights for currently selected column."""
    if not session.columns:
        return []
    selected_nodes = session.columns[session.selected_column_index].nodes
    return _column_row_heights(selected_nodes, render)


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


def _interactive_flow_board_renderable(console: Console, session: _BoardSession) -> RenderableType:
    """Build scrollable interactive flow board with fixed headers/footer."""
    if session.show_help_modal:
        return render_interactive_help_modal(
            _BOARD_HELP_ENTRIES,
            color_enabled=session.color_enabled,
        )

    prompt_line = None
    active_action = session.active_interactive_action
    if active_action is not None:
        prompt_line = build_footer_prompt_text(active_action.prompt_config.prompt)
    footer_height = (
        _INTERACTIVE_FOOTER_HEIGHT
        if prompt_line is None
        else _INTERACTIVE_FOOTER_HEIGHT_WITH_PROMPT
    )

    panel_content_width = _estimate_panel_content_width(console.width, len(session.columns))
    body_height = max(
        1,
        console.size.height - _INTERACTIVE_HEADER_HEIGHT - footer_height,
    )

    header = _build_board_header(session.columns)
    body, end_row = _build_board_body(session, panel_content_width, body_height)

    selected_nodes = session.columns[session.selected_column_index].nodes
    total_rows = max(len(selected_nodes), 1)
    visible_end_row = min(end_row, total_rows)
    search_text = session.search_text or "-"
    row_text = f"Rows {visible_end_row}/{total_rows} | Search: {search_text}"
    status = " ".join((session.status_message or "").splitlines())
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

    layout = Layout(name="board")
    layout.split_column(
        Layout(name="header", size=_INTERACTIVE_HEADER_HEIGHT),
        Layout(name="body"),
        Layout(name="footer", size=footer_height),
    )
    layout["header"].update(Group(header, Rule(style=footer_style)))
    layout["body"].update(body)
    status_text = Text(status, style=footer_style, no_wrap=True, overflow="ellipsis")
    if prompt_line is None:
        layout["footer"].update(Group(Rule(style=footer_style), footer_line, status_text))
    else:
        layout["footer"].update(
            Group(Rule(style=footer_style), footer_line, prompt_line, status_text),
        )
    return layout


def _build_board_header(columns: list[_BoardColumn]) -> Table:
    """Build interactive board header row from current columns."""
    header = Table(expand=True, box=None, show_lines=False, show_header=False, pad_edge=False)
    for _ in columns:
        header.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
    header_cells: list[Text] = []
    for column in columns:
        title_text = _render_column_title_text(column.title)
        title_text.overflow = "ellipsis"
        title_text.no_wrap = True
        header_cells.append(title_text)
    header.add_row(*header_cells)
    return header


def _build_board_body(
    session: _BoardSession,
    panel_content_width: int,
    body_height: int,
) -> tuple[Table, int]:
    """Build interactive board body and return visible end-row index."""
    body = Table(expand=True, box=None, show_lines=False, show_header=False, pad_edge=False)
    for _ in session.columns:
        body.add_column(ratio=1)

    render = _BoardPanelRenderConfig(
        width=panel_content_width,
        color_enabled=session.color_enabled,
        done_states=session.done_states,
        todo_states=session.todo_states,
    )

    selected_row_heights = _selected_column_row_heights(session, render)
    start_row, end_row, _used_lines = _sync_scroll_for_selection(
        session,
        selected_row_heights,
        body_height,
    )

    body_cells: list[RenderableType] = []
    for column_index, column in enumerate(session.columns):
        panels: list[RenderableType] = []
        if start_row >= len(column.nodes):
            body_cells.append(Text(""))
            continue

        column_end_row, _column_used_lines = _window_end_for_height(
            _column_row_heights(column.nodes, render),
            start_row,
            body_height,
        )
        if column_end_row < len(column.nodes):
            column_end_row += 1

        for row_index in range(start_row, column_end_row):
            if row_index >= len(column.nodes):
                continue

            node = column.nodes[row_index]
            highlighted = (
                column_index == session.selected_column_index
                and row_index == session.selected_row_index
            )
            panels.append(_build_task_panel(node, render, highlighted=highlighted))

        body_cells.append(Group(*panels) if panels else Text(""))

    body.add_row(*body_cells)
    return body, end_row


def _flow_board_key_bindings(
    session: _BoardSession,
) -> dict[str, SessionAction[_BoardSession]]:
    """Build interactive key bindings for flow board session."""
    return {
        "q": quit_view_action(),
        "ESC": quit_view_action(),
        "DOWN": view_action(lambda _session: _move_selection_vertical(session, 1)),
        "WHEEL-DOWN": view_action(lambda _session: _move_selection_vertical(session, 1)),
        "UP": view_action(lambda _session: _move_selection_vertical(session, -1)),
        "WHEEL-UP": view_action(lambda _session: _move_selection_vertical(session, -1)),
        "RIGHT": view_action(lambda _session: _move_selection_horizontal(session, 1)),
        "LEFT": view_action(lambda _session: _move_selection_horizontal(session, -1)),
        "ENTER": status_external_action(_edit_selected_task_in_external_editor),
        "a": PromptInteractiveAction(
            prompt_config=capture_template_prompt_config(),
            apply_with_input=_submit_board_capture_action,
            resolve_target=lambda current: current,
            options_factory=lambda _session: configured_capture_template_names(),
            can_activate=can_activate_configured_capture_templates,
            requires_live_pause=True,
        ),
        "$": status_noninteractive_action(_archive_selected_task),
        "/": PromptInteractiveAction(
            prompt_config=PromptActionConfig(
                prompt=FooterPromptState(label="Search text (blank clears)"),
                cancel_status="Search cancelled",
                invalid_status="Invalid search input",
            ),
            apply_with_input=_submit_board_search_action,
            preview_with_input=_preview_board_search_action,
            cancel_with_target=_cancel_board_search_action,
            resolve_target=lambda current: current,
            can_activate=_capture_board_search_prompt_state,
        ),
        "x": status_view_action(_clear_search),
        "S-LEFT": status_noninteractive_action(
            lambda _session: _apply_state_move(session, direction=-1),
        ),
        "S-RIGHT": status_noninteractive_action(
            lambda _session: _apply_state_move(session, direction=1),
        ),
        "S-UP": status_noninteractive_action(
            lambda _session: _apply_priority_shift(session, increase=True),
        ),
        "S-DOWN": status_noninteractive_action(
            lambda _session: _apply_priority_shift(session, increase=False),
        ),
    }


def _handle_interactive_key(session: _BoardSession, key: str) -> bool:
    """Handle one interactive keypress and return whether to continue."""
    consumed, next_help_modal = apply_help_modal_key(
        key,
        show_help_modal=session.show_help_modal,
    )
    session.show_help_modal = next_help_modal
    if consumed:
        return True

    result = dispatch_action_key(key, session, _flow_board_key_bindings(session))
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
                if _handle_active_prompt_input(session, live):
                    continue

                key = read_keypress(timeout_seconds=_INTERACTIVE_INPUT_TIMEOUT_SECONDS)
                if not key:
                    live.update(_interactive_flow_board_renderable(console, session), refresh=True)
                    continue

                bindings = _flow_board_key_bindings(session)
                if action_requires_live_pause(key, bindings):
                    live.stop()
                    should_continue = _handle_interactive_key(session, key)
                    live.start()
                else:
                    should_continue = _handle_interactive_key(session, key)

                if not should_continue:
                    break
                live.update(_interactive_flow_board_renderable(console, session), refresh=True)
    finally:
        set_mouse_reporting(False)


def _handle_active_prompt_input(session: _BoardSession, live: Live) -> bool:
    """Handle one board prompt event and return whether input was consumed."""
    if session.show_help_modal:
        return False
    return handle_active_interactive_action_input(
        session,
        pause_live=live.stop,
        refresh=lambda: live.update(
            _interactive_flow_board_renderable(live.console, session),
            refresh=True,
        ),
        resume_live=live.start,
    )


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
    if args.days < 0:
        raise typer.BadParameter("--days must be non-negative")
    args.max_results = _resolve_tasks_limit(args.max_results)

    with processing_status(console, color_enabled):
        nodes, discovered_todo_states, discovered_done_states = load_and_process_data(args)
        nodes = _filter_recent_completed_nodes(nodes, args.days)
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

    columns = _build_selector_board_columns(nodes, _resolve_column_specs(args))
    _render_static_flow_board(
        console,
        columns,
        _BoardStaticRenderInput(
            done_states=done_states,
            todo_states=todo_states,
            color_enabled=color_enabled,
        ),
    )


def register(app: typer.Typer) -> None:
    """Register the flow board command."""

    @app.command(
        "board",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
        help=interactive_help_command_text(
            "Display tasks as an interactive flow board.",
            _BOARD_HELP_ENTRIES,
        ),
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
        view: str | None = typer.Option(
            None,
            "--view",
            metavar="NAME",
            help="Configured board view name",
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
        days: int = typer.Option(
            7,
            "--days",
            metavar="N",
            help="Show completed tasks modified in last N days",
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
            view=view,
            width=width,
            max_results=max_results,
            offset=offset,
            days=days,
            order_by_level=order_by_level,
            order_by_file_order=order_by_file_order,
            order_by_file_order_reversed=order_by_file_order_reversed,
            order_by_priority=order_by_priority,
            order_by_timestamp_asc=order_by_timestamp_asc,
            order_by_timestamp_desc=order_by_timestamp_desc,
            with_tags_as_category=with_tags_as_category,
        )
        config_module.apply_config_defaults(args)
        config_module.log_applied_config_defaults(args, sys.argv[1:], "board")
        config_module.log_command_arguments(args, "board")
        run_flow_board(args)
