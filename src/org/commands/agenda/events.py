"""Agenda interactive event handlers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from org_parser.time import Clock, Timestamp

from org.cli_common import load_and_process_data, resolve_input_paths
from org.commands.archive import archive_heading_subtree_and_save
from org.commands.editor import edit_heading_subtree_in_external_editor
from org.commands.interactive_common import (
    FooterPromptState,
    HeadingLocator,
    InputEvent,
    InteractiveEvent,
    InteractivePromptState,
    TimeoutEvent,
    advance_timestamp_by_repeater,
    append_repeat_transition,
    apply_help_modal_key,
    create_interactive_prompt_state,
    handle_active_prompt_event,
    heading_locator,
    interactive_loop,
    local_now,
    resolve_heading_locator,
    set_timestamp_fields,
)
from org.commands.search_common import filter_nodes_by_search
from org.commands.tasks.capture import TasksCaptureArgs, capture_task
from org.commands.tasks.common import (
    PromptActionConfig,
    capture_template_prompt_config,
    clock_duration_prompt_config,
    configured_capture_template_names,
    duration_to_org_text,
    iter_descendants,
    load_document,
    parse_clock_duration,
    refile_prompt_config,
    resolve_capture_template_selection,
    resolve_refile_destination_input,
    resolve_todo_state_selection,
    save_document,
    state_selection_prompt_config,
    todo_states_for_heading,
)

from .layout import (
    AgendaRow,
    DayRowModel,
    RenderContext,
    _has_specific_time,
    _hide_interactive_day_row,
    _resolve_agenda_start_date,
    _selected_row_location,
    build_view_day_model,
    interactive_agenda_renderable,
)


if TYPE_CHECKING:
    from collections.abc import Callable

    from org_parser.document import Document, Heading
    from rich.console import Console

    from .command import AgendaArgs
    from .views import AgendaViewContext


logger = logging.getLogger("org")
_INTERACTIVE_INPUT_TIMEOUT_SECONDS = 1.0


@dataclass
class AgendaSession:
    """Interactive agenda session state."""

    args: AgendaArgs
    all_nodes: list[Heading]
    nodes: list[Heading]
    render: RenderContext
    start_date: date
    days: int
    now: datetime
    day_models: list[DayRowModel]
    row_locations: list[tuple[int, int]]
    selected_row_index: int
    scroll_offset: int
    status_message: str
    search_text: str
    view_ctx: AgendaViewContext
    search_prompt_previous_text: str | None = None
    show_help_modal: bool = False
    active_prompt: InteractivePromptState | None = None
    run_external: Callable[[Callable[[], None]], None] | None = None


def refresh_session(
    session: AgendaSession,
    preserve_identity: HeadingLocator | None,
) -> None:
    """Recompute day row models and restore selection when possible."""
    session.now = local_now()
    day_models: list[DayRowModel] = []
    row_locations: list[tuple[int, int]] = []

    for day_offset in range(session.days):
        day = session.start_date + timedelta(days=day_offset)
        day_model = build_view_day_model(
            session.nodes,
            day,
            session.now,
            session.view_ctx,
            session.args,
        )
        day_models.append(day_model)
        row_locations.extend(
            (len(day_models) - 1, row_index)
            for row_index, row in enumerate(day_model.rows)
            if not _hide_interactive_day_row(len(day_models) - 1, row_index, row)
        )

    session.day_models = day_models
    session.row_locations = row_locations
    if not row_locations:
        session.selected_row_index = 0
        return

    preserved_node = resolve_heading_locator(session.nodes, preserve_identity)
    if preserved_node is not None:
        for idx, (day_index, row_index) in enumerate(row_locations):
            row = day_models[day_index].rows[row_index]
            if row.node is preserved_node:
                session.selected_row_index = idx
                return

    if session.selected_row_index >= len(row_locations):
        session.selected_row_index = len(row_locations) - 1
    session.selected_row_index = max(session.selected_row_index, 0)


def refresh_visible_nodes(
    session: AgendaSession,
    preserve_identity: HeadingLocator | None,
) -> None:
    """Refresh visible agenda nodes and restore selected task identity when possible."""
    session.nodes = filter_nodes_by_search(session.all_nodes, session.search_text)
    refresh_session(session, preserve_identity)


def selected_task_row(session: AgendaSession) -> AgendaRow | None:
    """Return currently selected task row when selected row is a task."""
    location = _selected_row_location(session)
    if location is None:
        return None
    day_index, row_index = location
    row = session.day_models[day_index].rows[row_index]
    if row.kind != "task" or row.node is None:
        return None
    return row


def _refresh_session_if_minute_changed(session: AgendaSession) -> bool:
    """Refresh agenda rows when local wall-clock minute changes."""
    current_now = local_now().replace(second=0, microsecond=0)
    session_now = session.now.replace(second=0, microsecond=0)
    if current_now == session_now:
        return False
    preserve_identity = None
    selected_row = selected_task_row(session)
    if selected_row is not None and selected_row.node is not None:
        preserve_identity = heading_locator(selected_row.node)
    refresh_session(session, preserve_identity)
    return True


def _paths_refer_to_same_file(source_path: str, destination_path: str) -> bool:
    """Return whether two path strings point to the same file."""
    try:
        source_resolved = Path(source_path).expanduser().resolve(strict=False)
        destination_resolved = Path(destination_path).expanduser().resolve(strict=False)
    except OSError:
        source_resolved = Path(source_path).expanduser().absolute()
        destination_resolved = Path(destination_path).expanduser().absolute()
    return source_resolved == destination_resolved


def _move_selection(session: AgendaSession, step: int) -> None:
    """Move highlighted row selection forward/backward with wraparound."""
    if not session.row_locations:
        return
    session.selected_row_index = (session.selected_row_index + step) % len(session.row_locations)


def _shift_timestamp_by_days(timestamp: Timestamp, day_delta: int) -> None:
    """Shift one timestamp by a day delta."""
    shifted_start = timestamp.start + timedelta(days=day_delta)
    shifted_end = None if timestamp.end is None else timestamp.end + timedelta(days=day_delta)
    set_timestamp_fields(timestamp, shifted_start, shifted_end)


def _shift_timestamp_by_hours(timestamp: Timestamp, hour_delta: int) -> None:
    """Shift one timestamp by an hour delta."""
    shifted_start = timestamp.start + timedelta(hours=hour_delta)
    shifted_end = None if timestamp.end is None else timestamp.end + timedelta(hours=hour_delta)
    set_timestamp_fields(timestamp, shifted_start, shifted_end)


def _save_document_changes(document: Document) -> None:
    """Persist one mutated document to disk."""
    logger.info("Saving agenda edit file: %s", document.filename)
    save_document(document)


def _reload_session_nodes(session: AgendaSession) -> None:
    """Reload nodes through standard processing pipeline after mutations."""
    nodes, _, _ = load_and_process_data(session.args)
    session.all_nodes = nodes
    session.nodes = filter_nodes_by_search(nodes, session.search_text)


def _edit_selected_task_in_external_editor(session: AgendaSession) -> None:
    row = selected_task_row(session)
    if row is None or row.node is None:
        session.status_message = "Action available only on task rows"
        return
    preserve_identity = heading_locator(row.node)
    session.status_message = ""
    try:
        edit_result = edit_heading_subtree_in_external_editor(row.node)
    except typer.BadParameter as err:
        session.status_message = str(err)
        return
    if not edit_result.changed:
        session.status_message = "No changes."
        return
    _reload_session_nodes(session)
    refresh_session(session, preserve_identity)
    session.status_message = "Task updated"


def _archive_selected_task(session: AgendaSession) -> None:
    row = selected_task_row(session)
    if row is None or row.node is None:
        session.status_message = "Action available only on task rows"
        return
    session.status_message = ""
    try:
        archive_result = archive_heading_subtree_and_save(row.node, {})
    except typer.BadParameter as err:
        session.status_message = str(err)
        return
    preserve_identity = heading_locator(archive_result.heading)
    _reload_session_nodes(session)
    refresh_session(session, preserve_identity)
    session.status_message = "Task archived"


def _shift_planning_for_row(
    row: AgendaRow,
    *,
    day_delta: int,
) -> tuple[Timestamp | None, str]:
    node = row.node
    if node is None:
        return None, "Action available only on task rows"
    deadline_sources = {"overdue_deadline", "upcoming_deadline", "deadline_today"}
    scheduled_sources = {"scheduled", "repeat", "overdue_scheduled", "scheduled_untimed"}
    timestamp: Timestamp | None = None
    field_name = ""
    if row.source in deadline_sources:
        timestamp = node.deadline
        field_name = "deadline"
    elif row.source in scheduled_sources:
        timestamp = node.scheduled
        field_name = "scheduled"
    if timestamp is None:
        return None, "Selected task has no mutable planning timestamp"
    before = str(timestamp)
    _shift_timestamp_by_days(timestamp, day_delta)
    after = str(timestamp)
    logger.info(
        "Agenda shift date: file=%s title=%s id=%s field=%s before=%s after=%s",
        node.document.filename,
        node.title_text,
        node.id,
        field_name,
        before,
        after,
    )
    return timestamp, f"Shifted {field_name} by {day_delta:+d} day"


def shift_planning_time_for_row(
    row: AgendaRow,
    *,
    hour_delta: int,
) -> tuple[Timestamp | None, str]:
    """Shift the selected timed planning row by hours."""
    node = row.node
    if node is None:
        return None, "Action available only on task rows"
    timestamp: Timestamp | None = None
    field_name = ""
    if row.source == "scheduled":
        timestamp = node.scheduled
        field_name = "scheduled"
    elif row.source == "deadline_today":
        timestamp = node.deadline
        field_name = "deadline"
    if timestamp is None:
        return None, "Time shifting is available only for timed scheduled/deadline rows"
    if not _has_specific_time(timestamp):
        return None, "Selected planning timestamp has no specific hour"
    before = str(timestamp)
    _shift_timestamp_by_hours(timestamp, hour_delta)
    after = str(timestamp)
    logger.info(
        "Agenda shift time: file=%s title=%s id=%s field=%s before=%s after=%s",
        node.document.filename,
        node.title_text,
        node.id,
        field_name,
        before,
        after,
    )
    direction = "forward" if hour_delta > 0 else "backward"
    return timestamp, f"Shifted {field_name} {direction} by {abs(hour_delta)} hour"


def apply_state_change_with_value(session: AgendaSession, new_state: str) -> None:
    """Apply a TODO state change to the selected agenda task."""
    row = selected_task_row(session)
    if row is None or row.node is None:
        session.status_message = "Action available only on task rows"
        return
    heading = row.node
    old_state = heading.todo
    if old_state == new_state:
        session.status_message = "State unchanged"
        return
    action_now = local_now()
    heading.todo = new_state
    append_repeat_transition(heading, old_state, new_state, action_now)
    if heading.scheduled is not None and advance_timestamp_by_repeater(heading.scheduled):
        logger.info(
            "Agenda repeater advance: file=%s title=%s id=%s field=scheduled value=%s",
            heading.document.filename,
            heading.title_text,
            heading.id,
            heading.scheduled,
        )
    if heading.deadline is not None and advance_timestamp_by_repeater(heading.deadline):
        logger.info(
            "Agenda repeater advance: file=%s title=%s id=%s field=deadline value=%s",
            heading.document.filename,
            heading.title_text,
            heading.id,
            heading.deadline,
        )
    _save_document_changes(heading.document)
    preserve_identity = heading_locator(heading)
    _reload_session_nodes(session)
    refresh_session(session, preserve_identity)
    session.status_message = f"State updated: {old_state or '-'} -> {new_state}"


def apply_shift_date(session: AgendaSession, *, day_delta: int) -> None:
    """Shift the selected agenda task planning date by days."""
    row = selected_task_row(session)
    if row is None or row.node is None:
        session.status_message = "Action available only on task rows"
        return
    timestamp, status = _shift_planning_for_row(row, day_delta=day_delta)
    if timestamp is None:
        session.status_message = status
        return
    heading = row.node
    _save_document_changes(heading.document)
    preserve_identity = heading_locator(heading)
    _reload_session_nodes(session)
    refresh_session(session, preserve_identity)
    session.status_message = status


def _apply_shift_time(session: AgendaSession, *, hour_delta: int) -> None:
    row = selected_task_row(session)
    if row is None or row.node is None:
        session.status_message = "Action available only on task rows"
        return
    timestamp, status = shift_planning_time_for_row(row, hour_delta=hour_delta)
    if timestamp is None:
        session.status_message = status
        return
    heading = row.node
    _save_document_changes(heading.document)
    preserve_identity = heading_locator(heading)
    _reload_session_nodes(session)
    refresh_session(session, preserve_identity)
    session.status_message = status


def _move_heading_to_document(heading: Heading, destination: Document) -> None:
    parent = heading.parent
    if parent is None:
        raise ValueError("Cannot refile heading without parent")
    parent.children.remove(heading)
    destination.children.append(heading)
    heading.document = destination
    for descendant in iter_descendants(heading):
        descendant.document = destination


def apply_refile_with_value(session: AgendaSession, destination_input: str) -> None:
    """Refile the selected agenda task to the requested destination."""
    row = selected_task_row(session)
    if row is None or row.node is None:
        session.status_message = "Action available only on task rows"
        return
    current_files = resolve_input_paths(session.args.files)
    destination_path, validation_error = resolve_refile_destination_input(
        destination_input,
        current_files,
    )
    if destination_path is None and validation_error is None:
        session.status_message = "Refile cancelled"
        return
    if validation_error is not None:
        session.status_message = validation_error
        return
    if destination_path is None:
        session.status_message = "Refile cancelled"
        return
    try:
        destination_document = load_document(destination_path)
    except typer.BadParameter as err:
        session.status_message = str(err)
        return
    heading = row.node
    source_document = heading.document
    source_path = source_document.filename or ""
    destination_doc_path = destination_document.filename or destination_path
    if (
        source_path
        and destination_doc_path
        and _paths_refer_to_same_file(source_path, destination_doc_path)
    ):
        session.status_message = "Task already in destination file"
        return
    _move_heading_to_document(heading, destination_document)
    _save_document_changes(destination_document)
    if source_document is not destination_document:
        _save_document_changes(source_document)
    preserve_identity = heading_locator(heading)
    _reload_session_nodes(session)
    refresh_session(session, preserve_identity)
    session.status_message = f"Refiled task to {destination_doc_path}"


def apply_clock_entry_with_value(session: AgendaSession, duration_input: str) -> None:
    """Add a clock entry to the selected agenda task."""
    row = selected_task_row(session)
    if row is None or row.node is None:
        session.status_message = "Action available only on task rows"
        return
    duration_input = duration_input.strip()
    if not duration_input:
        session.status_message = "Clock action cancelled"
        return
    try:
        duration = parse_clock_duration(duration_input)
    except ValueError as err:
        session.status_message = str(err)
        return
    action_now = local_now()
    end_time = action_now.replace(second=0, microsecond=0)
    start_time = end_time - duration
    timestamp = Timestamp.from_source(
        f"[{start_time:%Y-%m-%d %a %H:%M}]--[{end_time:%Y-%m-%d %a %H:%M}]",
    )
    duration_text = duration_to_org_text(duration)
    row.node.clock_entries.append(Clock(timestamp=timestamp, duration=duration_text))
    _save_document_changes(row.node.document)
    preserve_identity = heading_locator(row.node)
    _reload_session_nodes(session)
    refresh_session(session, preserve_identity)
    session.status_message = f"Added clock entry ({duration_text})"


def _clear_search(session: AgendaSession) -> None:
    if not session.search_text:
        session.status_message = "Search already clear"
        return
    selected_row = selected_task_row(session)
    preserve_identity = None
    if selected_row is not None and selected_row.node is not None:
        preserve_identity = heading_locator(selected_row.node)
    session.search_text = ""
    refresh_visible_nodes(session, preserve_identity)
    session.status_message = "Search cleared"


def selected_row(session: AgendaSession) -> AgendaRow | None:
    """Return the currently selected agenda row."""
    location = _selected_row_location(session)
    if location is None:
        return None
    day_index, row_index = location
    return session.day_models[day_index].rows[row_index]


def _timetable_schedule_for_selected_row(session: AgendaSession) -> Timestamp | None:
    row = selected_row(session)
    if row is None:
        return None
    if row.kind == "task" and row.source not in {"scheduled", "deadline_today", "repeat"}:
        return None
    if row.kind not in {"task", "hour_marker", "now_marker"}:
        return None
    time_parts = row.time_text.split(":", 1)
    if len(time_parts) != 2 or not all(part.isdigit() for part in time_parts):
        return None
    hour = int(time_parts[0])
    minute = int(time_parts[1])
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    day_name = row.day.strftime("%a")
    return Timestamp.from_source(f"<{row.day:%Y-%m-%d} {day_name} {hour:02d}:{minute:02d}>")


def _apply_capture_task(session: AgendaSession, template_name: str) -> None:
    scheduled = _timetable_schedule_for_selected_row(session)
    if scheduled is None:
        session.status_message = "Capture is available only on timetable time rows"
        return
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
    capture_result.heading.scheduled = scheduled
    try:
        _save_document_changes(capture_result.document)
        _reload_session_nodes(session)
        refresh_session(session, heading_locator(capture_result.heading))
    except typer.BadParameter as err:
        session.status_message = str(err)
        return
    session.status_message = f"Task captured and scheduled for {scheduled}"


def _state_choices_for_selected_row(session: AgendaSession) -> list[str]:
    row = selected_task_row(session)
    if row is None or row.node is None:
        return []
    return todo_states_for_heading(row.node)


def _can_activate_agenda_state_prompt(session: AgendaSession) -> str | None:
    row = selected_task_row(session)
    if row is None or row.node is None:
        return "Action available only on task rows"
    if not _state_choices_for_selected_row(session):
        return "No TODO states defined"
    return None


def _can_activate_agenda_capture_prompt(session: AgendaSession) -> str | None:
    if _timetable_schedule_for_selected_row(session) is None:
        return "Capture is available only on timetable time rows"
    if not configured_capture_template_names():
        return "No capture templates configured"
    return None


def _apply_search_text(session: AgendaSession, search_text: str) -> None:
    selected_row = selected_task_row(session)
    preserve_identity = None
    if selected_row is not None and selected_row.node is not None:
        preserve_identity = heading_locator(selected_row.node)
    session.search_text = search_text
    refresh_visible_nodes(session, preserve_identity)
    session.status_message = (
        "Search cleared" if not search_text else f"{len(session.nodes)} matches"
    )


def create_agenda_session(
    args: AgendaArgs,
    nodes: list[Heading],
    render: RenderContext,
    view_ctx: AgendaViewContext,
) -> AgendaSession:
    """Create interactive session state for agenda."""
    session = AgendaSession(
        args=args,
        all_nodes=list(nodes),
        nodes=nodes,
        render=render,
        start_date=_resolve_agenda_start_date(args.date),
        days=args.days,
        now=local_now(),
        day_models=[],
        row_locations=[],
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
        search_text="",
        view_ctx=view_ctx,
        show_help_modal=False,
        active_prompt=None,
    )
    refresh_session(session, None)
    return session


def _set_start_date_relative(session: AgendaSession, *, day_delta: int) -> None:
    session.start_date += timedelta(days=day_delta)
    refresh_session(session, None)


def _activate_prompt(
    session: AgendaSession,
    config: PromptActionConfig,
    *,
    submit_value: Callable[[str], bool],
    preview_value: Callable[[str], None] | None = None,
    cancel: Callable[[], None] | None = None,
) -> None:
    session.active_prompt = create_interactive_prompt_state(
        config,
        submit_value=submit_value,
        preview_value=preview_value,
        cancel=cancel,
    )


def _activate_capture_prompt(session: AgendaSession) -> None:
    status_message = _can_activate_agenda_capture_prompt(session)
    if status_message is not None:
        session.status_message = status_message
        return
    template_names = configured_capture_template_names()
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


def _activate_search_prompt(session: AgendaSession) -> None:
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

    _activate_prompt(session, config, submit_value=_submit, preview_value=_preview, cancel=_cancel)


def _activate_state_selection_prompt(session: AgendaSession, states: list[str]) -> None:
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
        apply_state_change_with_value(session, selected_state)
        return False

    _activate_prompt(session, config, submit_value=_submit)


def _activate_value_prompt(
    session: AgendaSession,
    config: PromptActionConfig,
    apply_value: Callable[[str], None],
) -> None:
    def _submit(value: str) -> bool:
        value = value.strip()
        if not value:
            session.status_message = config.cancel_status
            return False
        apply_value(value)
        return False

    _activate_prompt(session, config, submit_value=_submit)


def _handle_capture_prompt_activation(session: AgendaSession) -> None:
    _activate_capture_prompt(session)


def _handle_search_prompt_activation(session: AgendaSession) -> None:
    _activate_search_prompt(session)


def _handle_state_prompt_activation(session: AgendaSession) -> None:
    status_message = _can_activate_agenda_state_prompt(session)
    if status_message is not None:
        session.status_message = status_message
        return
    _activate_state_selection_prompt(session, _state_choices_for_selected_row(session))


def _handle_refile_prompt_activation(session: AgendaSession) -> None:
    if selected_task_row(session) is None:
        session.status_message = "Action available only on task rows"
        return
    _activate_value_prompt(
        session,
        refile_prompt_config(resolve_input_paths(session.args.files)),
        lambda value: apply_refile_with_value(session, value),
    )


def _handle_clock_prompt_activation(session: AgendaSession) -> None:
    if selected_task_row(session) is None:
        session.status_message = "Action available only on task rows"
        return
    _activate_value_prompt(
        session,
        clock_duration_prompt_config(),
        lambda value: apply_clock_entry_with_value(session, value),
    )


def _handle_help_modal_event(session: AgendaSession, event: InteractiveEvent) -> bool:
    if not session.show_help_modal:
        return False
    if not isinstance(event, TimeoutEvent):
        session.show_help_modal = False
    return True


def _handle_navigation_key(session: AgendaSession, key: str) -> bool:
    handler = {
        "n": lambda: _move_selection(session, 1),
        "DOWN": lambda: _move_selection(session, 1),
        "WHEEL-DOWN": lambda: _move_selection(session, 1),
        "p": lambda: _move_selection(session, -1),
        "UP": lambda: _move_selection(session, -1),
        "WHEEL-UP": lambda: _move_selection(session, -1),
        "f": lambda: _set_start_date_relative(session, day_delta=session.days),
        "RIGHT": lambda: _set_start_date_relative(session, day_delta=session.days),
        "b": lambda: _set_start_date_relative(session, day_delta=-session.days),
        "LEFT": lambda: _set_start_date_relative(session, day_delta=-session.days),
    }.get(key)
    if handler is None:
        return False
    handler()
    return True


def _handle_mutation_key(
    session: AgendaSession,
    key: str,
    run_external: Callable[[Callable[[], None]], None],
) -> bool:
    handler = {
        "ENTER": lambda: run_external(lambda: _edit_selected_task_in_external_editor(session)),
        "$": lambda: _archive_selected_task(session),
        "x": lambda: _clear_search(session),
        "S-LEFT": lambda: apply_shift_date(session, day_delta=-1),
        "S-RIGHT": lambda: apply_shift_date(session, day_delta=1),
        "S-UP": lambda: _apply_shift_time(session, hour_delta=-1),
        "S-DOWN": lambda: _apply_shift_time(session, hour_delta=1),
    }.get(key)
    if handler is None:
        return False
    handler()
    return True


def _handle_prompt_activation_key(
    session: AgendaSession,
    key: str,
    _run_external_callback: Callable[[Callable[[], None]], None],
) -> bool:
    handler = {
        "a": _handle_capture_prompt_activation,
        "/": _handle_search_prompt_activation,
        "t": _handle_state_prompt_activation,
        "r": _handle_refile_prompt_activation,
        "c": _handle_clock_prompt_activation,
    }.get(key)
    if handler is None:
        return False
    handler(session)
    return True


def _handle_keypress_event(
    session: AgendaSession,
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
    """Run an external callback immediately."""
    callback()


def _run_external(session: AgendaSession, callback: Callable[[], None]) -> None:
    runner = session.run_external or passthrough_run_external
    runner(callback)


def handle_interactive_event(
    session: AgendaSession,
    event: InteractiveEvent,
    run_external: Callable[[Callable[[], None]], None],
) -> bool:
    """Handle one agenda interactive event."""
    if _handle_help_modal_event(session, event):
        return True
    if session.active_prompt is not None:
        return handle_active_prompt_event(session, event)
    if isinstance(event, TimeoutEvent):
        _refresh_session_if_minute_changed(session)
        return True
    if isinstance(event, InputEvent):
        return True
    return _handle_keypress_event(session, event.key, run_external)


def run_agenda_interactive(console: Console, session: AgendaSession) -> None:
    """Run the interactive agenda loop."""
    run_external: list[Callable[[Callable[[], None]], None]] = [passthrough_run_external]

    def _bind_run_external(callback: Callable[[Callable[[], None]], None]) -> None:
        run_external[0] = callback
        session.run_external = callback

    session.run_external = run_external[0]
    interactive_loop(
        console=console,
        render=lambda: interactive_agenda_renderable(console, session),
        on_event=lambda event: handle_interactive_event(session, event, run_external[0]),
        bind_run_external=_bind_run_external,
        timeout_seconds=_INTERACTIVE_INPUT_TIMEOUT_SECONDS,
    )
