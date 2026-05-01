"""Tasks list command."""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import click
import typer
from rich.console import Group
from rich.live import Live
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from org import config as config_module
from org.cli_common import load_and_process_data
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
from org.commands.tasks.common import (
    PlanningTimestampField,
    planning_field_label,
    replace_heading_tags_from_csv,
    replace_planning_timestamp_from_raw,
    save_document,
)
from org.output_format import (
    DEFAULT_OUTPUT_THEME,
    OutputFormat,
    OutputFormatError,
    OutputOperation,
    PreparedOutput,
    _build_org_document,
    _json_output_payload,
    _normalize_syntax_theme,
    _org_to_pandoc_format,
    _parse_pandoc_args,
    _prepare_output,
    print_prepared_output,
)
from org.tui import (
    TaskLineConfig,
    build_console,
    format_task_line,
    lines_to_text,
    processing_status,
    setup_output,
)


if TYPE_CHECKING:
    from org_parser.document import Document, Heading
    from rich.console import Console


logger = logging.getLogger("org")
_HIGHLIGHT_ROW_STYLE = "on grey23"


@dataclass
class ListArgs:
    """Arguments for the tasks list command."""

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
    details: bool
    offset: int
    order_by_level: bool
    order_by_file_order: bool
    order_by_file_order_reversed: bool
    order_by_priority: bool
    order_by_timestamp_asc: bool
    order_by_timestamp_desc: bool
    with_tags_as_category: bool
    out: str
    out_theme: str
    pandoc_args: str | None
    noninteractive: bool = False


@dataclass(frozen=True)
class TasksListRenderInput:
    """Render input for tasks list output formatters."""

    nodes: list[Heading]
    console: Console
    color_enabled: bool
    done_states: list[str]
    todo_states: list[str]
    details: bool
    line_width: int | None
    out_theme: str


@dataclass(frozen=True)
class _TasksListSessionData:
    """Loaded task data shared by static and interactive renderers."""

    nodes: list[Heading]
    todo_states: list[str]
    done_states: list[str]
    color_enabled: bool


_TasksListHeadingIdentity = HeadingIdentity


@dataclass
class _TasksListSession:
    """Interactive tasks-list session state."""

    args: ListArgs
    all_nodes: list[Heading]
    visible_nodes: list[Heading]
    todo_states: list[str]
    done_states: list[str]
    color_enabled: bool
    selected_index: int
    scroll_offset: int
    status_message: str
    search_text: str


class TasksListOutputFormatter(Protocol):
    """Formatter interface for the tasks list command."""

    include_filenames: bool

    def prepare(self, data: TasksListRenderInput) -> PreparedOutput:
        """Prepare tasks list output for rendering."""
        ...


def _format_short_task_list(data: TasksListRenderInput) -> str:
    """Return formatted short list of tasks."""
    lines = [
        format_task_line(
            node,
            TaskLineConfig(
                color_enabled=data.color_enabled,
                done_states=data.done_states,
                todo_states=data.todo_states,
                line_width=data.line_width,
            ),
        )
        for node in data.nodes
    ]
    return lines_to_text(lines)


def _prepare_detailed_task_list(nodes: list[Heading], out_theme: str) -> PreparedOutput:
    """Prepare detailed list of tasks with syntax highlighting."""
    theme = _normalize_syntax_theme(out_theme)
    operations: list[OutputOperation] = []
    for idx, node in enumerate(nodes):
        if idx > 0:
            operations.append(OutputOperation(kind="console_print", text="", markup=False))
        filename = node.document.filename or "unknown"
        node_text = str(node).rstrip()
        org_block = f"# {filename}\n{node_text}" if node_text else f"# {filename}"
        operations.append(
            OutputOperation(
                kind="console_print",
                renderable=Syntax(
                    org_block,
                    "org",
                    theme=theme,
                    line_numbers=False,
                    word_wrap=True,
                ),
            ),
        )
    return PreparedOutput(operations=tuple(operations))


class OrgTasksListOutputFormatter:
    """Org output formatter for tasks list command."""

    include_filenames = True

    def prepare(self, data: TasksListRenderInput) -> PreparedOutput:
        """Prepare tasks list output in org or short-list form."""
        if not data.nodes:
            return PreparedOutput(
                operations=(
                    OutputOperation(kind="console_print", text="No results", markup=False),
                ),
            )

        if data.details:
            return _prepare_detailed_task_list(data.nodes, data.out_theme)

        output = _format_short_task_list(data)
        if output:
            return PreparedOutput(
                operations=(
                    OutputOperation(
                        kind="print_output",
                        text=output,
                        color_enabled=data.color_enabled,
                        end="",
                    ),
                ),
            )

        return PreparedOutput(
            operations=(OutputOperation(kind="console_print", text="No results", markup=False),),
        )


class PandocTasksListOutputFormatter:
    """Pandoc-based output formatter for tasks list command."""

    include_filenames = False

    def __init__(self, output_format: str, pandoc_args: str | None) -> None:
        """Initialize formatter options for pandoc-based task rendering."""
        self.output_format = output_format
        self.pandoc_args = _parse_pandoc_args(pandoc_args)

    def prepare(self, data: TasksListRenderInput) -> PreparedOutput:
        """Prepare tasks list output and convert it with pandoc."""
        if not data.nodes:
            return PreparedOutput(
                operations=(
                    OutputOperation(kind="console_print", text="No results", markup=False),
                ),
            )
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
        """Prepare tasks list output as JSON."""
        payload = _json_output_payload(list(data.nodes))
        return _prepare_output(
            json.dumps(payload, ensure_ascii=True),
            data.color_enabled,
            OutputFormat.JSON,
            data.out_theme,
        )


_ORG_TASKS_LIST_FORMATTER = OrgTasksListOutputFormatter()
_JSON_TASKS_LIST_FORMATTER = JsonTasksListOutputFormatter()


def get_tasks_list_formatter(
    output_format: str,
    pandoc_args: str | None,
) -> TasksListOutputFormatter:
    """Return tasks list formatter for selected output format."""
    normalized_output = output_format.strip().lower()
    if normalized_output == OutputFormat.ORG:
        return _ORG_TASKS_LIST_FORMATTER
    if normalized_output == OutputFormat.JSON:
        return _JSON_TASKS_LIST_FORMATTER
    return PandocTasksListOutputFormatter(normalized_output, pandoc_args)


def _resolve_tasks_limit(max_results: int | None, console_height: int) -> int:
    """Resolve effective tasks limit, defaulting to all available tasks."""
    del console_height
    if max_results is None:
        return sys.maxsize
    return max_results


def _line_count(text: str) -> int:
    """Return visual line count for a rendered text block."""
    if not text:
        return 0
    return len(text.splitlines())


def _should_page_prepared_output(
    prepared_output: PreparedOutput,
    *,
    details: bool,
    console_height: int,
) -> bool:
    """Estimate whether prepared output should be displayed via pager."""
    if details:
        return True

    estimated_lines = 0
    for operation in prepared_output.operations:
        if operation.kind == "print_output" and operation.text is not None:
            estimated_lines += _line_count(operation.text)
            continue

        if operation.kind == "plain_write" and operation.text is not None:
            estimated_lines += max(1, _line_count(operation.text))
            continue

        if operation.kind == "console_print":
            if operation.renderable is not None:
                return True
            if operation.text is not None:
                estimated_lines += max(1, _line_count(operation.text))

    return estimated_lines > console_height


def _run_tasks_list_static(
    console: Console,
    args: ListArgs,
    data: _TasksListSessionData,
) -> None:
    """Render tasks list using non-interactive output formatters."""
    requested_limit = args.max_results

    output_format = args.out.strip().lower()
    should_use_pager = output_format == OutputFormat.ORG and (
        requested_limit is None or requested_limit >= console.height
    )
    try:
        formatter = get_tasks_list_formatter(args.out, args.pandoc_args)
    except OutputFormatError as exc:
        raise click.UsageError(str(exc)) from exc

    try:
        prepared_output = formatter.prepare(
            TasksListRenderInput(
                nodes=data.nodes,
                console=console,
                color_enabled=data.color_enabled,
                done_states=data.done_states,
                todo_states=data.todo_states,
                details=args.details,
                line_width=console.width,
                out_theme=args.out_theme,
            ),
        )
    except OutputFormatError as exc:
        raise click.UsageError(str(exc)) from exc

    if should_use_pager and _should_page_prepared_output(
        prepared_output,
        details=args.details,
        console_height=console.height,
    ):
        with console.pager(styles=data.color_enabled):
            print_prepared_output(console, prepared_output)
        return

    print_prepared_output(console, prepared_output)


def _ensure_selection_bounds(session: _TasksListSession) -> None:
    """Clamp selected index to currently visible rows."""
    if not session.visible_nodes:
        session.selected_index = 0
        session.scroll_offset = 0
        return

    session.selected_index = min(max(session.selected_index, 0), len(session.visible_nodes) - 1)


def _selected_node(session: _TasksListSession) -> Heading | None:
    """Return currently selected heading or None when selection is empty."""
    if not session.visible_nodes:
        return None
    if session.selected_index < 0 or session.selected_index >= len(session.visible_nodes):
        return None
    return session.visible_nodes[session.selected_index]


def _node_search_text(node: Heading) -> str:
    """Build search text from one node without including child subtrees."""
    parts: list[str] = [
        str(node.title_text),
        str(node.body_text),
        str(node.todo or ""),
        str(node.priority or ""),
        str(node.id or ""),
    ]

    parts.extend(str(tag) for tag in node.tags)
    parts.extend(str(tag) for tag in node.heading_tags)

    for key, value in node.properties.items():
        parts.append(str(key))
        parts.append(str(value))

    parts.extend(
        str(timestamp)
        for timestamp in (node.scheduled, node.deadline, node.closed)
        if timestamp is not None
    )

    parts.extend(str(repeat) for repeat in node.repeats)
    return "\n".join(parts)


def _filter_nodes_by_search(nodes: list[Heading], search_text: str) -> list[Heading]:
    """Filter nodes by case-insensitive substring match over one node's own text."""
    normalized_search = search_text.strip().casefold()
    if not normalized_search:
        return list(nodes)

    return [node for node in nodes if normalized_search in _node_search_text(node).casefold()]


def _refresh_visible_nodes(
    session: _TasksListSession,
    preserve_identity: _TasksListHeadingIdentity | None,
) -> None:
    """Refresh visible nodes and restore selection when possible."""
    session.visible_nodes = _filter_nodes_by_search(session.all_nodes, session.search_text)
    if not session.visible_nodes:
        session.selected_index = 0
        session.scroll_offset = 0
        return

    if preserve_identity is not None:
        for index, node in enumerate(session.visible_nodes):
            if heading_identity_matches(node, preserve_identity):
                session.selected_index = index
                _ensure_selection_bounds(session)
                return

    _ensure_selection_bounds(session)


def _reload_session_nodes(
    session: _TasksListSession,
    preserve_identity: _TasksListHeadingIdentity | None,
) -> bool:
    """Reload session nodes via standard processing pipeline."""
    try:
        nodes, todo_states, done_states = load_and_process_data(session.args)
    except typer.BadParameter as err:
        session.status_message = str(err)
        return False

    session.all_nodes = nodes
    session.todo_states = todo_states
    session.done_states = done_states
    _refresh_visible_nodes(session, preserve_identity)
    return True


def _save_document_changes(document: Document) -> None:
    """Persist one mutated document to disk."""
    logger.info("Saving tasks list edit file: %s", document.filename)
    document.sync_heading_id_index()
    save_document(document)


def _persist_and_reload_selected(
    session: _TasksListSession,
    node: Heading,
    status_message: str,
) -> None:
    """Save selected heading document and refresh session state."""
    preserve_identity = heading_identity(node)
    try:
        _save_document_changes(node.document)
    except typer.BadParameter as err:
        session.status_message = str(err)
        return

    if _reload_session_nodes(session, preserve_identity):
        session.status_message = status_message


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
    viewport_height = max(5, console.size.height - 3)
    _ensure_selection_bounds(session)
    _sync_scroll(session, viewport_height)

    window = session.visible_nodes[session.scroll_offset : session.scroll_offset + viewport_height]
    table = Table.grid(expand=True)
    table.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
    for index, node in enumerate(window, start=session.scroll_offset):
        row_style = _HIGHLIGHT_ROW_STYLE if index == session.selected_index else ""
        table.add_row(
            _build_task_row_text(node, session, line_width=console.size.width),
            style=row_style,
        )

    for _ in range(viewport_height - len(window)):
        table.add_row(Text(""))

    controls = (
        "Up/Down, n/p, Wheel move"
        " | / search"
        " | x clear"
        " | Enter view"
        " | t state"
        " | Shift+Up/Down priority"
        " | g tags"
        " | s scheduled"
        " | d deadline"
        " | c closed"
        " | q/Esc quit"
    )
    selected_row = session.selected_index + 1 if session.visible_nodes else 0
    total_rows = len(session.visible_nodes)
    search_text = session.search_text or "-"
    row_text = f"Rows {selected_row}/{total_rows} | Search: {search_text}"
    status = session.status_message or ""
    footer_style = "dim" if session.color_enabled else ""

    footer_line = Table.grid(expand=True)
    footer_line.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
    footer_line.add_column(ratio=4, justify="right", no_wrap=True, overflow="ellipsis")
    footer_line.add_row(
        Text(row_text, style=footer_style, no_wrap=True, overflow="ellipsis"),
        Text(controls, style=footer_style, no_wrap=True, overflow="ellipsis"),
    )

    return Group(
        table,
        Rule(style=footer_style),
        footer_line,
        Text(status, style=footer_style, no_wrap=True, overflow="ellipsis"),
    )


def _choose_state(console: Console, heading: Heading) -> str | None:
    """Prompt for a new TODO state from document-defined states."""
    states = list(dict.fromkeys(heading.document.all_states))
    if not states:
        return None

    console.print("Choose new TODO state:")
    for idx, state in enumerate(states, start=1):
        console.print(f"{idx}) {state}")

    selection = console.input("State number or value (blank cancels): ").strip()
    if not selection:
        return None

    if selection.isdigit():
        index = int(selection) - 1
        if 0 <= index < len(states):
            return states[index]
        return None

    if selection in states:
        return selection
    return None


def _open_selected_task_detail(console: Console, session: _TasksListSession) -> None:
    """Open selected task detail in pager."""
    node = _selected_node(session)
    if node is None:
        session.status_message = "Action available only on task rows"
        return

    session.status_message = ""
    set_mouse_reporting(False)
    try:
        open_task_detail_in_pager(console, node, color_enabled=session.color_enabled)
    finally:
        set_mouse_reporting(True)


def _prompt_search(console: Console, session: _TasksListSession) -> None:
    """Prompt for interactive full-text search input."""
    selected = _selected_node(session)
    preserve_identity = heading_identity(selected) if selected is not None else None
    search_value = console.input("Search text (blank clears): ").strip()
    session.search_text = search_value
    _refresh_visible_nodes(session, preserve_identity)
    if not search_value:
        session.status_message = "Search cleared"
        return
    session.status_message = f"{len(session.visible_nodes)} matches"


def _clear_search(session: _TasksListSession) -> None:
    """Clear active interactive search and restore full visible list."""
    if not session.search_text:
        session.status_message = "Search already clear"
        return

    selected = _selected_node(session)
    preserve_identity = heading_identity(selected) if selected is not None else None
    session.search_text = ""
    _refresh_visible_nodes(session, preserve_identity)
    session.status_message = "Search cleared"


def _apply_state_change(console: Console, session: _TasksListSession) -> None:
    """Apply TODO state transition on selected task."""
    node = _selected_node(session)
    if node is None:
        session.status_message = "Action available only on task rows"
        return

    new_state = _choose_state(console, node)
    if new_state is None:
        session.status_message = "State change cancelled"
        return

    old_state = node.todo
    if old_state == new_state:
        session.status_message = "State unchanged"
        return

    node.todo = new_state
    append_repeat_transition(node, old_state, new_state, local_now())
    _persist_and_reload_selected(
        session,
        node,
        f"State updated: {old_state or '-'} -> {new_state}",
    )


def _apply_priority_shift(session: _TasksListSession, *, increase: bool) -> None:
    """Increase or decrease priority one step for selected task."""
    node = _selected_node(session)
    if node is None:
        session.status_message = "Action available only on task rows"
        return

    old_priority = node.priority
    new_priority = shift_priority(old_priority, increase=increase)
    if old_priority == new_priority:
        session.status_message = "Priority unchanged"
        return

    node.priority = new_priority
    _persist_and_reload_selected(
        session,
        node,
        f"Priority updated: {old_priority or '-'} -> {new_priority or '-'}",
    )


def _apply_tags_edit(console: Console, session: _TasksListSession) -> None:
    """Prompt and replace tags on selected task."""
    node = _selected_node(session)
    if node is None:
        session.status_message = "Action available only on task rows"
        return

    raw_tags = console.input("Tags CSV (blank clears): ")
    try:
        _old_tags, _new_tags, changed = replace_heading_tags_from_csv(node, raw_tags)
    except typer.BadParameter as err:
        session.status_message = str(err)
        return

    if not changed:
        session.status_message = "Tags unchanged"
        return

    _persist_and_reload_selected(session, node, "Tags updated")


def _apply_planning_timestamp_edit(
    console: Console,
    session: _TasksListSession,
    *,
    field: PlanningTimestampField,
) -> None:
    """Prompt and update one planning timestamp field on selected task."""
    node = _selected_node(session)
    if node is None:
        session.status_message = "Action available only on task rows"
        return

    prompt_label = planning_field_label(field)
    raw_timestamp = console.input(f"{prompt_label} (blank clears): ")
    try:
        _old_timestamp, _new_timestamp, changed = replace_planning_timestamp_from_raw(
            node,
            field,
            raw_timestamp,
        )
    except typer.BadParameter as err:
        session.status_message = str(err)
        return

    if not changed:
        session.status_message = f"{prompt_label} unchanged"
        return

    _persist_and_reload_selected(session, node, f"{prompt_label} updated")


def _apply_scheduled_edit(console: Console, session: _TasksListSession) -> None:
    """Prompt and update scheduled timestamp on selected task."""
    _apply_planning_timestamp_edit(console, session, field="scheduled")


def _apply_deadline_edit(console: Console, session: _TasksListSession) -> None:
    """Prompt and update deadline timestamp on selected task."""
    _apply_planning_timestamp_edit(console, session, field="deadline")


def _apply_closed_edit(console: Console, session: _TasksListSession) -> None:
    """Prompt and update closed timestamp on selected task."""
    _apply_planning_timestamp_edit(console, session, field="closed")


def _move_selection(session: _TasksListSession, step: int) -> None:
    """Move selection forward/backward with wraparound."""
    if not session.visible_nodes:
        return
    session.selected_index = (session.selected_index + step) % len(session.visible_nodes)


def _tasks_list_key_bindings(
    console: Console,
    session: _TasksListSession,
) -> dict[str, KeyBinding]:
    """Build interactive key bindings for tasks list session."""
    return {
        "q": KeyBinding(lambda: False),
        "ESC": KeyBinding(lambda: False),
        "n": key_binding_for_action(lambda: _move_selection(session, 1)),
        "DOWN": key_binding_for_action(lambda: _move_selection(session, 1)),
        "WHEEL-DOWN": key_binding_for_action(lambda: _move_selection(session, 1)),
        "p": key_binding_for_action(lambda: _move_selection(session, -1)),
        "UP": key_binding_for_action(lambda: _move_selection(session, -1)),
        "WHEEL-UP": key_binding_for_action(lambda: _move_selection(session, -1)),
        "ENTER": key_binding_for_action(
            lambda: _open_selected_task_detail(console, session),
            requires_live_pause=True,
        ),
        "/": key_binding_for_action(
            lambda: _prompt_search(console, session),
            requires_live_pause=True,
        ),
        "x": key_binding_for_action(lambda: _clear_search(session)),
        "t": key_binding_for_action(
            lambda: _apply_state_change(console, session),
            requires_live_pause=True,
        ),
        "S-UP": key_binding_for_action(lambda: _apply_priority_shift(session, increase=True)),
        "S-DOWN": key_binding_for_action(lambda: _apply_priority_shift(session, increase=False)),
        "g": key_binding_for_action(
            lambda: _apply_tags_edit(console, session),
            requires_live_pause=True,
        ),
        "s": key_binding_for_action(
            lambda: _apply_scheduled_edit(console, session),
            requires_live_pause=True,
        ),
        "d": key_binding_for_action(
            lambda: _apply_deadline_edit(console, session),
            requires_live_pause=True,
        ),
        "c": key_binding_for_action(
            lambda: _apply_closed_edit(console, session),
            requires_live_pause=True,
        ),
    }


def _handle_interactive_key(console: Console, session: _TasksListSession, key: str) -> bool:
    """Handle one interactive keypress and return whether to continue."""
    result = dispatch_key_binding(key, _tasks_list_key_bindings(console, session))
    if result.handled:
        return result.continue_loop

    if key:
        session.status_message = f"Unsupported key: {key}"
    return True


def _create_tasks_list_session(args: ListArgs, data: _TasksListSessionData) -> _TasksListSession:
    """Create interactive tasks list session state."""
    session = _TasksListSession(
        args=args,
        all_nodes=list(data.nodes),
        visible_nodes=list(data.nodes),
        todo_states=list(data.todo_states),
        done_states=list(data.done_states),
        color_enabled=data.color_enabled,
        selected_index=0,
        scroll_offset=0,
        status_message="",
        search_text="",
    )
    _ensure_selection_bounds(session)
    return session


def _run_tasks_list_interactive(
    console: Console,
    args: ListArgs,
    data: _TasksListSessionData,
) -> None:
    """Run interactive tasks-list UI session."""
    if not data.nodes:
        console.print("No results", markup=False)
        return

    session = _create_tasks_list_session(args, data)
    set_mouse_reporting(True)
    try:
        with Live(
            _interactive_tasks_list_renderable(console, session),
            console=console,
            screen=True,
            refresh_per_second=12,
            auto_refresh=False,
        ) as live:
            while True:
                key = read_keypress(timeout_seconds=0.2)
                if not key:
                    live.update(_interactive_tasks_list_renderable(console, session), refresh=True)
                    continue

                if key_binding_requires_live_pause(key, _tasks_list_key_bindings(console, session)):
                    live.stop()
                    should_continue = _handle_interactive_key(console, session, key)
                    live.start()
                else:
                    should_continue = _handle_interactive_key(console, session, key)

                if not should_continue:
                    break
                live.update(_interactive_tasks_list_renderable(console, session), refresh=True)
    finally:
        set_mouse_reporting(False)


def _is_cli_option_present(argv: list[str], option: str) -> bool:
    """Return True when a long option token is present in argv."""
    return any(token == option or token.startswith(f"{option}=") for token in argv)


def _is_interactive_tty() -> bool:
    """Return whether both stdin and stdout are attached to a TTY."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def _effective_noninteractive_mode(args: ListArgs) -> bool:
    """Resolve whether tasks list should run in non-interactive mode."""
    out_is_org = args.out.strip().lower() == OutputFormat.ORG
    return args.noninteractive or args.details or not out_is_org or not _is_interactive_tty()


def run_tasks_list(args: ListArgs) -> None:
    """Run the tasks list command."""
    color_enabled = setup_output(args)
    console = build_console(color_enabled, args.width)
    if args.offset < 0:
        raise typer.BadParameter("--offset must be non-negative")
    if args.max_results is not None and args.max_results < 0:
        raise typer.BadParameter("--limit must be non-negative")
    args.max_results = _resolve_tasks_limit(args.max_results, console.height)

    with processing_status(console, color_enabled):
        nodes, todo_states, done_states = load_and_process_data(args)
    session_data = _TasksListSessionData(
        nodes=nodes,
        todo_states=todo_states,
        done_states=done_states,
        color_enabled=color_enabled,
    )

    if not _effective_noninteractive_mode(args):
        _run_tasks_list_interactive(console, args, session_data)
        return

    _run_tasks_list_static(console, args, session_data)


def register(app: typer.Typer) -> None:
    """Register the tasks list command."""

    @app.command(
        "list",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )
    def tasks_list(  # noqa: PLR0913
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
            min=50,
            help="Override auto-derived console width (minimum: 50)",
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
        details: bool = typer.Option(
            False,
            "--details",
            help="Show full org node details",
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
        out: str = typer.Option(
            OutputFormat.ORG,
            "--out",
            help="Output format: org, json, or any pandoc writer format",
        ),
        out_theme: str = typer.Option(
            DEFAULT_OUTPUT_THEME,
            "--out-theme",
            help="Syntax theme for highlighted output blocks",
        ),
        pandoc_args: str | None = typer.Option(
            None,
            "--pandoc-args",
            metavar="ARGS",
            help="Additional arguments forwarded to pandoc export",
        ),
    ) -> None:
        """List tasks matching filters."""
        args = ListArgs(
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
            details=details,
            offset=offset,
            order_by_level=order_by_level,
            order_by_file_order=order_by_file_order,
            order_by_file_order_reversed=order_by_file_order_reversed,
            order_by_priority=order_by_priority,
            order_by_timestamp_asc=order_by_timestamp_asc,
            order_by_timestamp_desc=order_by_timestamp_desc,
            with_tags_as_category=with_tags_as_category,
            out=out,
            out_theme=out_theme,
            pandoc_args=pandoc_args,
        )
        config_module.apply_config_defaults(args)
        details_switch_present = _is_cli_option_present(sys.argv[1:], "--details")
        out_switch_present = _is_cli_option_present(sys.argv[1:], "--out")
        args.noninteractive = (
            details_switch_present or out_switch_present or not _is_interactive_tty()
        )
        config_module.log_applied_config_defaults(args, sys.argv[1:], "tasks list")
        config_module.log_command_arguments(args, "tasks list")
        run_tasks_list(args)
