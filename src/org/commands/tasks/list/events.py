"""Tasks list interactive event handlers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import typer

from org.cli_common import load_and_process_data
from org.commands.archive import archive_heading_subtree_and_save
from org.commands.editor import edit_heading_subtree_in_external_editor
from org.commands.interactive_common import (
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
    heading_locator,
    local_now,
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


if TYPE_CHECKING:
    from collections.abc import Callable

    from org_parser.document import Document, Heading

    from .command import ListArgs, _TasksListSessionData


logger = logging.getLogger("org")


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


def _refresh_visible_nodes(
    session: _TasksListSession,
    preserve_identity: HeadingLocator | None,
) -> None:
    """Refresh visible nodes and restore selection when possible."""
    session.visible_nodes = filter_nodes_by_search(session.all_nodes, session.search_text)
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


def create_tasks_list_session(args: ListArgs, data: _TasksListSessionData) -> _TasksListSession:
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


TasksListSession = _TasksListSession
TasksListHelpEntries = _TASKS_LIST_HELP_ENTRIES
ensure_selection_bounds = _ensure_selection_bounds
selected_node = _selected_node
refresh_visible_nodes = _refresh_visible_nodes
reload_session_nodes = _reload_session_nodes
save_document_changes = _save_document_changes
persist_and_reload_selected = _persist_and_reload_selected
edit_selected_task_in_external_editor = _edit_selected_task_in_external_editor
archive_selected_task = _archive_selected_task
apply_capture_task = _apply_capture_task
clear_search = _clear_search
apply_state_change_with_value = _apply_state_change_with_value
apply_priority_shift = _apply_priority_shift
apply_tags_edit = _apply_tags_edit
apply_planning_timestamp_edit = _apply_planning_timestamp_edit
state_choices_for_selected_node = _state_choices_for_selected_node
can_activate_state_prompt = _can_activate_state_prompt
apply_search_text = _apply_search_text
move_selection = _move_selection


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


def _activate_capture_prompt(session: _TasksListSession) -> None:
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
        _apply_planning_timestamp_edit(session, field=field, raw_timestamp=value)
        return False

    _activate_prompt(session, config, submit_value=_submit)


def _activate_state_selection_prompt(session: _TasksListSession, states: list[str]) -> None:
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
    _activate_capture_prompt(session)


def _handle_search_prompt_activation(session: _TasksListSession) -> None:
    _activate_search_prompt(session)


def _handle_state_prompt_activation(session: _TasksListSession) -> None:
    status_message = _can_activate_state_prompt(session)
    if status_message is not None:
        session.status_message = status_message
        return
    _activate_state_selection_prompt(session, _state_choices_for_selected_node(session))


def _handle_tags_prompt_activation(session: _TasksListSession) -> None:
    _activate_tags_prompt(session)


def _handle_scheduled_prompt_activation(session: _TasksListSession) -> None:
    _activate_planning_prompt(session, "scheduled")


def _handle_deadline_prompt_activation(session: _TasksListSession) -> None:
    _activate_planning_prompt(session, "deadline")


def _handle_closed_prompt_activation(session: _TasksListSession) -> None:
    _activate_planning_prompt(session, "closed")


def _handle_active_prompt_event(session: _TasksListSession, event: InteractiveEvent) -> bool:
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
    if not session.show_help_modal:
        return False
    if not isinstance(event, TimeoutEvent):
        session.show_help_modal = False
    return True


def _handle_navigation_key(session: _TasksListSession, key: str) -> bool:
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
    effective_run_external = passthrough_run_external if run_external is None else run_external
    consumed, next_help_modal = apply_help_modal_key(key, show_help_modal=session.show_help_modal)
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


def passthrough_run_external(callback: Callable[[], None]) -> None:
    callback()


def _run_external(session: _TasksListSession, callback: Callable[[], None]) -> None:
    runner = session.run_external or passthrough_run_external
    runner(callback)


def handle_interactive_event(
    session: _TasksListSession,
    event: InteractiveEvent,
    run_external: Callable[[Callable[[], None]], None],
) -> bool:
    if _handle_help_modal_event(session, event):
        return True
    if session.active_prompt is not None:
        return _handle_active_prompt_event(session, event)
    if isinstance(event, TimeoutEvent):
        return True
    if isinstance(event, InputEvent):
        return True
    return _handle_keypress_event(session, event.key, run_external)


__all__ = [
    name
    for name in globals()
    if name.startswith(("_handle_", "_activate_"))
    or name
    in {
        "_TASKS_LIST_HELP_ENTRIES",
        "_TasksListSession",
        "create_tasks_list_session",
        "TasksListHelpEntries",
        "ensure_selection_bounds",
        "selected_node",
        "refresh_visible_nodes",
        "reload_session_nodes",
        "save_document_changes",
        "persist_and_reload_selected",
        "edit_selected_task_in_external_editor",
        "archive_selected_task",
        "apply_capture_task",
        "clear_search",
        "apply_state_change_with_value",
        "apply_priority_shift",
        "apply_tags_edit",
        "apply_planning_timestamp_edit",
        "state_choices_for_selected_node",
        "can_activate_state_prompt",
        "apply_search_text",
        "move_selection",
        "_ensure_selection_bounds",
        "_move_selection",
        "_selected_node",
        "passthrough_run_external",
        "_run_external",
        "handle_interactive_event",
    }
]
