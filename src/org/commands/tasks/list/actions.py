"""Tasks list interactive event handlers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import typer
from org_parser.document import Heading

from org.commands.tasks.capture import TasksCaptureArgs, capture_task
from org.commands.tasks.common import (
    PlanningTimestampField,
    planning_field_label,
    replace_heading_tags_from_csv,
    replace_planning_timestamp_from_raw,
    todo_states_for_heading,
)
from org.db.errors import RepositoryError
from org.db.repository import (
    OrgRepository,
    build_repository_query_plan,
    cli_error_from_repository_error,
)
from org.logic.archive import archive_heading_subtree_and_save
from org.logic.edit import edit_heading_subtree_in_external_editor
from org.logic.search import filter_nodes_by_search
from org.logic.tasks import (
    HeadingLocator,
    append_repeat_transition,
    heading_locator,
    resolve_heading_locator,
    shift_priority,
)
from org.logic.time import advance_timestamp_by_repeater, local_now
from org.query.engine.errors import QueryParseError, QueryRuntimeError
from org.tui.help import InteractiveHelpEntry


if TYPE_CHECKING:
    from org_parser.document import Document

    from org.config.app import AppConfig

    from .command import ListArgs, _TasksListSessionData


logger = logging.getLogger("org")


@dataclass
class TasksListSession:
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
    app_config: AppConfig
    repository: OrgRepository


TASKS_LIST_HELP_ENTRIES = [
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


def ensure_selection_bounds(session: TasksListSession) -> None:
    """Clamp selected index to currently visible rows."""
    if not session.visible_nodes:
        session.selected_index = 0
        session.scroll_offset = 0
        return

    session.selected_index = min(max(session.selected_index, 0), len(session.visible_nodes) - 1)


def selected_node(session: TasksListSession) -> Heading | None:
    """Return currently selected heading or None when selection is empty."""
    if not session.visible_nodes:
        return None
    if session.selected_index < 0 or session.selected_index >= len(session.visible_nodes):
        return None
    return session.visible_nodes[session.selected_index]


def refresh_visible_nodes(
    session: TasksListSession,
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
        ensure_selection_bounds(session)
        return

    ensure_selection_bounds(session)


def reload_session_nodes(
    session: TasksListSession,
    preserve_identity: HeadingLocator | None,
) -> bool:
    """Reload session nodes via standard processing pipeline."""
    try:
        plan = build_repository_query_plan(session.args, session.app_config, include_ordering=True)
        repository = session.repository
        results = repository.query(plan.stages, plan.context)
        nodes = [value for value in results if isinstance(value, Heading)]
        limit = session.args.max_results
        if limit is not None:
            nodes = nodes[session.args.offset : session.args.offset + limit]
    except (RepositoryError, QueryParseError, QueryRuntimeError, typer.BadParameter) as err:
        session.status_message = str(cli_error_from_repository_error(err))
        return False

    session.all_nodes = nodes
    session.todo_states = repository.todo_states
    session.done_states = repository.done_states
    refresh_visible_nodes(session, preserve_identity)
    return True


def save_document_changes(session: TasksListSession, document: Document) -> None:
    """Persist one mutated document to disk."""
    logger.info("Saving tasks list edit file: %s", document.filename)
    session.repository.save_document(document.filename or "")


def persist_and_reload_selected(
    session: TasksListSession,
    node: Heading,
    status_message: str,
) -> None:
    """Save selected heading document and refresh session state."""
    preserve_identity = heading_locator(node)
    try:
        save_document_changes(session, node.document)
    except (RepositoryError, typer.BadParameter) as err:
        session.status_message = str(cli_error_from_repository_error(err))
        return

    if reload_session_nodes(session, preserve_identity):
        session.status_message = status_message


def edit_selected_task_in_external_editor(session: TasksListSession) -> None:
    """Edit selected task subtree in configured external editor."""
    node = selected_node(session)
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

    if reload_session_nodes(session, preserve_identity):
        session.status_message = "Task updated"


def archive_selected_task(session: TasksListSession) -> None:
    """Archive selected task subtree using shared archive-location rules."""
    node = selected_node(session)
    if node is None:
        session.status_message = "Action available only on task rows"
        return

    session.status_message = ""
    try:
        archive_result = archive_heading_subtree_and_save(node, {}, session.repository)
    except (RepositoryError, typer.BadParameter) as err:
        session.status_message = str(cli_error_from_repository_error(err))
        return

    preserve_identity = heading_locator(archive_result.heading)
    if reload_session_nodes(session, preserve_identity):
        session.status_message = "Task archived"


def apply_capture_task(session: TasksListSession, template_name: str) -> None:
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
        capture_result = capture_task(capture_args, session.app_config.tasks.capture.templates)
    except KeyboardInterrupt:
        session.status_message = "Capture cancelled"
        return
    except typer.BadParameter as err:
        session.status_message = str(err)
        return

    try:
        if reload_session_nodes(session, heading_locator(capture_result.heading)):
            session.status_message = "Task captured"
    except typer.BadParameter as err:
        session.status_message = str(err)


def clear_search(session: TasksListSession) -> None:
    """Clear active interactive search and restore full visible list."""
    if not session.search_text:
        session.status_message = "Search already clear"
        return

    selected = selected_node(session)
    preserve_identity = heading_locator(selected) if selected is not None else None
    session.search_text = ""
    refresh_visible_nodes(session, preserve_identity)
    session.status_message = "Search cleared"


def apply_state_change_with_value(session: TasksListSession, new_state: str) -> None:
    """Apply TODO state transition on selected task."""
    node = selected_node(session)
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
    persist_and_reload_selected(
        session,
        node,
        f"State updated: {old_state or '-'} -> {new_state}",
    )


def apply_priority_shift(session: TasksListSession, *, increase: bool) -> None:
    """Increase or decrease priority one step for selected task."""
    node = selected_node(session)
    if node is None:
        session.status_message = "Action available only on task rows"
        return

    old_priority = node.priority
    new_priority = shift_priority(old_priority, increase=increase)
    if old_priority == new_priority:
        session.status_message = "Priority unchanged"
        return

    node.priority = new_priority
    persist_and_reload_selected(
        session,
        node,
        f"Priority updated: {old_priority or '-'} -> {new_priority or '-'}",
    )


def apply_tags_edit(session: TasksListSession, raw_tags: str) -> None:
    """Apply tags edit using submitted footer prompt value."""
    node = selected_node(session)
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

    persist_and_reload_selected(session, node, "Tags updated")


def apply_planning_timestamp_edit(
    session: TasksListSession,
    *,
    field: PlanningTimestampField,
    raw_timestamp: str,
) -> None:
    """Prompt and update one planning timestamp field on selected task."""
    node = selected_node(session)
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

    persist_and_reload_selected(session, node, f"{prompt_label} updated")


def state_choices_for_selected_node(session: TasksListSession) -> list[str]:
    """Return TODO-state choices for selected task."""
    node = selected_node(session)
    if node is None:
        return []
    return todo_states_for_heading(node)


def can_activate_state_prompt(session: TasksListSession) -> str | None:
    """Validate preconditions for opening state prompt."""
    if selected_node(session) is None:
        return "Action available only on task rows"
    if not state_choices_for_selected_node(session):
        return "No TODO states defined"
    return None


def apply_search_text(session: TasksListSession, search_text: str) -> None:
    """Apply search text to visible tasks and update match status."""
    selected = selected_node(session)
    preserve_identity = heading_locator(selected) if selected is not None else None
    session.search_text = search_text
    refresh_visible_nodes(session, preserve_identity)
    session.status_message = (
        "Search cleared" if not search_text else f"{len(session.visible_nodes)} matches"
    )


def move_selection(session: TasksListSession, step: int) -> None:
    """Move selection forward/backward with wraparound."""
    if not session.visible_nodes:
        return
    session.selected_index = (session.selected_index + step) % len(session.visible_nodes)


def create_tasks_list_session(
    args: ListArgs,
    config: AppConfig,
    data: _TasksListSessionData,
) -> TasksListSession:
    """Create interactive tasks list session state."""
    session = TasksListSession(
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
        app_config=config,
        repository=data.repository,
    )
    ensure_selection_bounds(session)
    return session
