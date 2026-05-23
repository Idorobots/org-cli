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
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from org import config as config_module
from org.cli_common import load_and_process_data
from org.commands.archive import archive_heading_subtree_and_save
from org.commands.editor import edit_heading_subtree_in_external_editor
from org.commands.interactive_common import (
    INTERACTIVE_HELP_FOOTER_HINT,
    FooterPromptState,
    HeadingLocator,
    InputEvent,
    InteractiveEvent,
    InteractiveHelpEntry,
    InteractivePromptState,
    KeypressEvent,
    TimeoutEvent,
    advance_timestamp_by_repeater,
    append_repeat_transition,
    apply_help_modal_key,
    apply_prompt_event,
    build_footer_prompt_text,
    heading_locator,
    interactive_help_command_text,
    interactive_loop,
    local_now,
    render_interactive_help_modal,
    resolve_heading_locator,
    shift_priority,
)
from org.commands.search_common import filter_nodes_by_search
from org.commands.tasks.capture import TasksCaptureArgs, capture_task
from org.commands.tasks.common import (
    PlanningTimestampField,
    PromptActionConfig,
    capture_template_prompt_config,
    configured_capture_template_names,
    planning_field_label,
    planning_prompt_config,
    replace_heading_tags_from_csv,
    replace_planning_timestamp_from_raw,
    resolve_capture_template_selection,
    resolve_todo_state_selection,
    save_document,
    state_selection_prompt_config,
    tags_prompt_config,
    todo_states_for_heading,
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
    from collections.abc import Callable

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
    search_prompt_previous_text: str | None = None
    show_help_modal: bool = False
    active_prompt: InteractivePromptState | None = None
    run_external: Callable[[Callable[[], None]], None] | None = None


_TASKS_LIST_HELP_ENTRIES = [
    InteractiveHelpEntry("Esc/q", "Exit the task list and return to the shell."),
    InteractiveHelpEntry(
        "Up/Down, n/p, Wheel",
        "Move selection through visible tasks while keeping the selected row in view.",
    ),
    InteractiveHelpEntry(
        "/",
        "Open search prompt; filter visible tasks by heading/body/properties text.",
    ),
    InteractiveHelpEntry("x", "Clear the active search filter and restore full results."),
    InteractiveHelpEntry(
        "Enter",
        "Open the selected task subtree in the external editor workflow.",
    ),
    InteractiveHelpEntry(
        "a",
        "Capture a new task from configured templates, then reload the list.",
    ),
    InteractiveHelpEntry(
        "$",
        "Archive the selected task subtree using standard archive rules.",
    ),
    InteractiveHelpEntry(
        "t",
        "Prompt for and apply a TODO state transition on the selected task.",
    ),
    InteractiveHelpEntry(
        "S-Up/S-Down",
        "Increase or decrease priority across A/B/C/none for the selected task.",
    ),
    InteractiveHelpEntry(
        "g",
        "Prompt for CSV tags and replace selected task tags (blank clears).",
    ),
    InteractiveHelpEntry(
        "s / d / c",
        "Prompt and set or clear scheduled, deadline, or closed timestamps.",
    ),
]


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


def _filter_nodes_by_search(nodes: list[Heading], search_text: str) -> list[Heading]:
    """Filter nodes by case-insensitive substring match over one node's own text."""
    return filter_nodes_by_search(nodes, search_text)


def _refresh_visible_nodes(
    session: _TasksListSession,
    preserve_identity: HeadingLocator | None,
) -> None:
    """Refresh visible nodes and restore selection when possible."""
    session.visible_nodes = _filter_nodes_by_search(session.all_nodes, session.search_text)
    if not session.visible_nodes:
        session.selected_index = 0
        session.scroll_offset = 0
        return

    preserved_node = resolve_heading_locator(session.visible_nodes, preserve_identity)
    if preserved_node is not None:
        session.selected_index = session.visible_nodes.index(preserved_node)
        _ensure_selection_bounds(session)
        return

    _ensure_selection_bounds(session)


def _reload_session_nodes(
    session: _TasksListSession,
    preserve_identity: HeadingLocator | None,
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
    save_document(document)


def _persist_and_reload_selected(
    session: _TasksListSession,
    node: Heading,
    status_message: str,
) -> None:
    """Save selected heading document and refresh session state."""
    preserve_identity = heading_locator(node)
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
    table = viewport_table

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
        return Group(table, Rule(style=footer_style), footer_line, status_text)
    return Group(table, Rule(style=footer_style), footer_line, prompt_line, status_text)


def _edit_selected_task_in_external_editor(session: _TasksListSession) -> None:
    """Edit selected task subtree in configured external editor."""
    node = _selected_node(session)
    if node is None:
        session.status_message = "Action available only on task rows"
        return

    preserve_identity = heading_locator(node)
    session.status_message = ""
    try:
        edit_result = edit_heading_subtree_in_external_editor(node)
    except typer.BadParameter as err:
        session.status_message = str(err)
        return

    if not edit_result.changed:
        session.status_message = "No changes."
        return

    if _reload_session_nodes(session, preserve_identity):
        session.status_message = "Task updated"


def _archive_selected_task(session: _TasksListSession) -> None:
    """Archive selected task subtree using shared archive-location rules."""
    node = _selected_node(session)
    if node is None:
        session.status_message = "Action available only on task rows"
        return

    session.status_message = ""
    try:
        archive_result = archive_heading_subtree_and_save(node, {})
    except typer.BadParameter as err:
        session.status_message = str(err)
        return

    preserve_identity = heading_locator(archive_result.heading)
    if _reload_session_nodes(session, preserve_identity):
        session.status_message = "Task archived"


def _apply_capture_task(session: _TasksListSession, template_name: str) -> None:
    """Capture a new task and reload list session."""
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
        if _reload_session_nodes(session, heading_locator(capture_result.heading)):
            session.status_message = "Task captured"
    except typer.BadParameter as err:
        session.status_message = str(err)


def _clear_search(session: _TasksListSession) -> None:
    """Clear active interactive search and restore full visible list."""
    if not session.search_text:
        session.status_message = "Search already clear"
        return

    selected = _selected_node(session)
    preserve_identity = heading_locator(selected) if selected is not None else None
    session.search_text = ""
    _refresh_visible_nodes(session, preserve_identity)
    session.status_message = "Search cleared"


def _apply_state_change_with_value(session: _TasksListSession, new_state: str) -> None:
    """Apply TODO state transition on selected task."""
    node = _selected_node(session)
    if node is None:
        session.status_message = "Action available only on task rows"
        return

    old_state = node.todo
    if old_state == new_state:
        session.status_message = "State unchanged"
        return

    node.todo = new_state
    append_repeat_transition(node, old_state, new_state, local_now())
    if node.scheduled is not None:
        advance_timestamp_by_repeater(node.scheduled)
    if node.deadline is not None:
        advance_timestamp_by_repeater(node.deadline)
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


def _apply_tags_edit(session: _TasksListSession, raw_tags: str) -> None:
    """Apply tags edit using submitted footer prompt value."""
    node = _selected_node(session)
    if node is None:
        session.status_message = "Action available only on task rows"
        return

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
    session: _TasksListSession,
    *,
    field: PlanningTimestampField,
    raw_timestamp: str,
) -> None:
    """Prompt and update one planning timestamp field on selected task."""
    node = _selected_node(session)
    if node is None:
        session.status_message = "Action available only on task rows"
        return

    prompt_label = planning_field_label(field)
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


def _state_choices_for_selected_node(session: _TasksListSession) -> list[str]:
    """Return TODO-state choices for selected task."""
    node = _selected_node(session)
    if node is None:
        return []
    return todo_states_for_heading(node)


def _can_activate_state_prompt(session: _TasksListSession) -> str | None:
    """Validate preconditions for opening state prompt."""
    if _selected_node(session) is None:
        return "Action available only on task rows"
    if not _state_choices_for_selected_node(session):
        return "No TODO states defined"
    return None


def _apply_search_text(session: _TasksListSession, search_text: str) -> None:
    """Apply search text to visible tasks and update match status."""
    selected = _selected_node(session)
    preserve_identity = heading_locator(selected) if selected is not None else None
    session.search_text = search_text
    _refresh_visible_nodes(session, preserve_identity)
    session.status_message = (
        "Search cleared" if not search_text else f"{len(session.visible_nodes)} matches"
    )


def _move_selection(session: _TasksListSession, step: int) -> None:
    """Move selection forward/backward with wraparound."""
    if not session.visible_nodes:
        return
    session.selected_index = (session.selected_index + step) % len(session.visible_nodes)


def _activate_prompt(
    session: _TasksListSession,
    config: PromptActionConfig,
    *,
    submit_value: Callable[[str], bool],
    preview_value: Callable[[str], None] | None = None,
    cancel: Callable[[], None] | None = None,
) -> None:
    """Attach one active footer prompt to the tasks list session."""

    def _submit() -> bool:
        active_prompt = session.active_prompt
        if active_prompt is None:
            return False
        return submit_value(active_prompt.prompt.value)

    def _preview() -> None:
        active_prompt = session.active_prompt
        if active_prompt is None or preview_value is None:
            return
        preview_value(active_prompt.prompt.value)

    session.active_prompt = InteractivePromptState(
        prompt=FooterPromptState(label=config.prompt.label),
        cancel_status=config.cancel_status,
        invalid_status=config.invalid_status,
        submit_callback=_submit,
        preview=None if preview_value is None else _preview,
        cancel=cancel,
    )


def _activate_capture_prompt(
    session: _TasksListSession,
) -> None:
    """Activate capture-template prompt when templates are configured."""
    template_names = configured_capture_template_names()
    if not template_names:
        session.status_message = "No capture templates configured"
        return

    config = capture_template_prompt_config()

    def _submit(value: str) -> bool:
        value = value.strip()
        template_name = resolve_capture_template_selection(value, template_names)
        if template_name is None and not value:
            session.status_message = config.cancel_status
            return False
        if template_name is None:
            session.status_message = config.invalid_status
            return True
        _run_external(session, lambda: _apply_capture_task(session, template_name))
        return False

    _activate_prompt(session, config, submit_value=_submit)


def _activate_search_prompt(session: _TasksListSession) -> None:
    """Activate search prompt and preserve current search text for cancellation."""
    session.search_prompt_previous_text = session.search_text
    config = PromptActionConfig(
        prompt=FooterPromptState(label="Search text (blank clears)"),
        cancel_status="Search cancelled",
        invalid_status="Invalid search input",
    )

    def _submit(value: str) -> bool:
        session.search_prompt_previous_text = None
        _apply_search_text(session, value.strip())
        return False

    def _preview(value: str) -> None:
        _apply_search_text(session, value.strip())

    def _cancel() -> None:
        previous_text = session.search_prompt_previous_text or ""
        session.search_prompt_previous_text = None
        _apply_search_text(session, previous_text)
        session.status_message = config.cancel_status

    _activate_prompt(
        session,
        config,
        submit_value=_submit,
        preview_value=_preview,
        cancel=_cancel,
    )


def _activate_tags_prompt(session: _TasksListSession) -> None:
    """Activate tags editing prompt for the selected task."""
    if _selected_node(session) is None:
        session.status_message = "Action available only on task rows"
        return

    config = tags_prompt_config()

    def _submit(value: str) -> bool:
        _apply_tags_edit(session, value)
        return False

    _activate_prompt(session, config, submit_value=_submit)


def _activate_planning_prompt(session: _TasksListSession, field: PlanningTimestampField) -> None:
    """Activate one planning timestamp prompt for the selected task."""
    if _selected_node(session) is None:
        session.status_message = "Action available only on task rows"
        return

    config = planning_prompt_config(field)

    def _submit(value: str) -> bool:
        _apply_planning_timestamp_edit(
            session,
            field=field,
            raw_timestamp=value,
        )
        return False

    _activate_prompt(session, config, submit_value=_submit)


def _activate_state_selection_prompt(
    session: _TasksListSession,
    states: list[str],
) -> None:
    """Activate TODO-state selection prompt for the selected task."""
    config = state_selection_prompt_config(states)

    def _submit(value: str) -> bool:
        value = value.strip()
        selected_state = resolve_todo_state_selection(value, states)
        if selected_state is None and not value:
            session.status_message = config.cancel_status
            return False
        if selected_state is None:
            session.status_message = config.invalid_status
            return True
        _apply_state_change_with_value(session, selected_state)
        return False

    _activate_prompt(session, config, submit_value=_submit)


def _handle_capture_prompt_activation(session: _TasksListSession) -> None:
    """Activate capture-template prompt for the current tasks-list session."""
    _activate_capture_prompt(session)


def _handle_search_prompt_activation(session: _TasksListSession) -> None:
    """Activate search prompt for the current tasks-list session."""
    _activate_search_prompt(session)


def _handle_state_prompt_activation(session: _TasksListSession) -> None:
    """Activate TODO-state selection prompt for the selected task."""
    status_message = _can_activate_state_prompt(session)
    if status_message is not None:
        session.status_message = status_message
        return
    _activate_state_selection_prompt(session, _state_choices_for_selected_node(session))


def _handle_tags_prompt_activation(session: _TasksListSession) -> None:
    """Activate tags prompt for the selected task."""
    _activate_tags_prompt(session)


def _handle_scheduled_prompt_activation(session: _TasksListSession) -> None:
    """Activate scheduled timestamp prompt for the selected task."""
    _activate_planning_prompt(session, "scheduled")


def _handle_deadline_prompt_activation(session: _TasksListSession) -> None:
    """Activate deadline timestamp prompt for the selected task."""
    _activate_planning_prompt(session, "deadline")


def _handle_closed_prompt_activation(session: _TasksListSession) -> None:
    """Activate closed timestamp prompt for the selected task."""
    _activate_planning_prompt(session, "closed")


def _handle_active_prompt_event(session: _TasksListSession, event: InteractiveEvent) -> bool:
    """Apply one event to the active tasks-list prompt."""
    active_prompt = session.active_prompt
    if active_prompt is None:
        return True
    if isinstance(event, TimeoutEvent):
        return True
    if isinstance(event, KeypressEvent) and event.key == "ESC":
        if active_prompt.cancel is not None:
            active_prompt.cancel()
        else:
            session.status_message = active_prompt.cancel_status
        session.active_prompt = None
        return True

    prompt_result = apply_prompt_event(active_prompt.prompt, event)
    if prompt_result.submitted:
        keep_open = active_prompt.submit_callback()
        if not keep_open:
            session.active_prompt = None
        return True
    if prompt_result.changed and active_prompt.preview is not None:
        active_prompt.preview()
    return True


def _handle_help_modal_event(session: _TasksListSession, event: InteractiveEvent) -> bool:
    """Handle help modal dismissal and return whether consumed."""
    if not session.show_help_modal:
        return False
    if not isinstance(event, TimeoutEvent):
        session.show_help_modal = False
    return True


def _handle_navigation_key(session: _TasksListSession, key: str) -> bool:
    """Handle navigation-only keys and return whether consumed."""
    handler = {
        "n": lambda: _move_selection(session, 1),
        "DOWN": lambda: _move_selection(session, 1),
        "WHEEL-DOWN": lambda: _move_selection(session, 1),
        "p": lambda: _move_selection(session, -1),
        "UP": lambda: _move_selection(session, -1),
        "WHEEL-UP": lambda: _move_selection(session, -1),
    }.get(key)
    if handler is None:
        return False
    handler()
    return True


def _handle_mutation_key(
    session: _TasksListSession,
    key: str,
    run_external: Callable[[Callable[[], None]], None],
) -> bool:
    """Handle immediate action keys and return whether consumed."""
    handler = {
        "ENTER": lambda: run_external(lambda: _edit_selected_task_in_external_editor(session)),
        "$": lambda: _archive_selected_task(session),
        "x": lambda: _clear_search(session),
        "S-UP": lambda: _apply_priority_shift(session, increase=True),
        "S-DOWN": lambda: _apply_priority_shift(session, increase=False),
    }.get(key)
    if handler is None:
        return False
    handler()
    return True


def _handle_prompt_activation_key(
    session: _TasksListSession,
    key: str,
    _run_external_callback: Callable[[Callable[[], None]], None],
) -> bool:
    """Handle keys that open interactive prompts and return whether consumed."""
    handler = {
        "a": _handle_capture_prompt_activation,
        "/": _handle_search_prompt_activation,
        "t": _handle_state_prompt_activation,
        "g": _handle_tags_prompt_activation,
        "s": _handle_scheduled_prompt_activation,
        "d": _handle_deadline_prompt_activation,
        "c": _handle_closed_prompt_activation,
    }.get(key)
    if handler is None:
        return False
    handler(session)
    return True


def _handle_keypress_event(
    session: _TasksListSession,
    key: str,
    run_external: Callable[[Callable[[], None]], None] | None = None,
) -> bool:
    """Handle one non-prompt keypress and return whether to continue."""
    effective_run_external = _passthrough_run_external if run_external is None else run_external
    consumed, next_help_modal = apply_help_modal_key(
        key,
        show_help_modal=session.show_help_modal,
    )
    session.show_help_modal = next_help_modal
    if consumed:
        return True
    if key in {"q", "ESC"}:
        return False
    if _handle_navigation_key(session, key):
        return True
    if _handle_mutation_key(session, key, effective_run_external):
        return True
    if _handle_prompt_activation_key(session, key, effective_run_external):
        return True
    if key and key != "IGNORE":
        session.status_message = f"Unsupported key: {key}"
    return True


def _passthrough_run_external(callback: Callable[[], None]) -> None:
    """Run one callback inline outside the shared interactive loop."""
    callback()


def _run_external(session: _TasksListSession, callback: Callable[[], None]) -> None:
    """Run one callback through the session's current external-runner hook."""
    runner = session.run_external or _passthrough_run_external
    runner(callback)


def _handle_interactive_event(
    session: _TasksListSession,
    event: InteractiveEvent,
    run_external: Callable[[Callable[[], None]], None],
) -> bool:
    """Handle one interactive event and return whether to continue."""
    if _handle_help_modal_event(session, event):
        return True

    if session.active_prompt is not None:
        return _handle_active_prompt_event(session, event)

    if isinstance(event, TimeoutEvent):
        return True
    if isinstance(event, InputEvent):
        return True

    return _handle_keypress_event(session, event.key, run_external)


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
        show_help_modal=False,
        active_prompt=None,
        run_external=None,
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

    run_external: list[Callable[[Callable[[], None]], None]] = [_passthrough_run_external]

    def _bind_run_external(callback: Callable[[Callable[[], None]], None]) -> None:
        run_external[0] = callback
        session.run_external = callback

    session.run_external = run_external[0]

    interactive_loop(
        render=lambda: _interactive_tasks_list_renderable(console, session),
        on_event=lambda event: _handle_interactive_event(session, event, run_external[0]),
        bind_run_external=_bind_run_external,
        timeout_seconds=None,
    )


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
        help=interactive_help_command_text(
            "List tasks matching filters.",
            _TASKS_LIST_HELP_ENTRIES,
        ),
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
