"""Agenda interactive event handlers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from org_parser.document import Heading
from org_parser.time import Clock, Timestamp

from org.commands.tasks.capture import TasksCaptureArgs, capture_task
from org.commands.tasks.common import (
    duration_to_org_text,
    iter_descendants,
    parse_clock_duration,
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
)
from org.logic.time import advance_timestamp_by_repeater, local_now, set_timestamp_fields
from org.query.engine.errors import QueryParseError, QueryRuntimeError

from .ui import (
    AgendaColumnWidths,
    AgendaRow,
    DayRowModel,
    RenderContext,
    ViewportRow,
    build_interactive_artifacts,
    build_view_day_model,
    has_specific_time,
    resolve_agenda_start_date,
    selected_row_location,
)


if TYPE_CHECKING:
    from collections.abc import Callable

    from org_parser.document import Document

    from org.config.app import AppConfig

    from .command import AgendaArgs
    from .views import AgendaViewContext


logger = logging.getLogger("org")


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
    interactive_rows: list[ViewportRow]
    column_widths: AgendaColumnWidths
    row_locations: list[tuple[int, int]]
    selected_row_index: int
    scroll_offset: int
    status_message: str
    search_text: str
    view_ctx: AgendaViewContext
    app_config: AppConfig
    repository: OrgRepository
    run_external: Callable[[Callable[[], None]], None] | None = None


@dataclass(frozen=True)
class AgendaSessionData:
    """Prepared agenda session inputs shared with the app layer."""

    nodes: list[Heading]
    render: RenderContext
    view_ctx: AgendaViewContext
    repository: OrgRepository


def refresh_session(
    session: AgendaSession,
    preserve_identity: HeadingLocator | None,
) -> None:
    """Recompute day row models and restore selection when possible."""
    session.now = local_now()
    day_models: list[DayRowModel] = []

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

    session.day_models = day_models
    session.row_locations, session.interactive_rows, session.column_widths = (
        build_interactive_artifacts(
            day_models,
            session.render,
        )
    )
    if not session.row_locations:
        session.selected_row_index = 0
        return

    preserved_node = resolve_heading_locator(session.nodes, preserve_identity)
    if preserved_node is not None:
        for idx, (day_index, row_index) in enumerate(session.row_locations):
            row = day_models[day_index].rows[row_index]
            if row.node is preserved_node:
                session.selected_row_index = idx
                return

    if session.selected_row_index >= len(session.row_locations):
        session.selected_row_index = len(session.row_locations) - 1
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
    location = selected_row_location(session)
    if location is None:
        return None
    day_index, row_index = location
    row = session.day_models[day_index].rows[row_index]
    if row.kind != "task" or row.node is None:
        return None
    return row


def refresh_session_if_minute_changed(session: AgendaSession) -> bool:
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


def move_selection(session: AgendaSession, step: int) -> None:
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


def _save_document_changes(session: AgendaSession, document: Document) -> None:
    """Persist one mutated document to disk."""
    logger.info("Saving agenda edit file: %s", document.filename)
    session.repository.save_document(document.filename or "")


def _reload_session_nodes(session: AgendaSession) -> None:
    """Reload nodes through standard processing pipeline after mutations."""
    plan = build_repository_query_plan(session.args, session.app_config, include_ordering=True)
    repository = session.repository
    results = repository.query(plan.stages, plan.context)
    nodes = [value for value in results if isinstance(value, Heading)]
    limit = session.args.max_results
    if limit is not None:
        nodes = nodes[session.args.offset : session.args.offset + limit]
    session.all_nodes = nodes
    session.nodes = filter_nodes_by_search(nodes, session.search_text)


def edit_selected_task_in_external_editor(session: AgendaSession) -> None:
    """Open the selected agenda task in the external editor workflow."""
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


def archive_selected_task(session: AgendaSession) -> None:
    """Archive the currently selected agenda task subtree."""
    row = selected_task_row(session)
    if row is None or row.node is None:
        session.status_message = "Action available only on task rows"
        return
    session.status_message = ""
    try:
        archive_result = archive_heading_subtree_and_save(
            row.node,
            {},
            session.repository,
        )
    except (RepositoryError, typer.BadParameter) as err:
        session.status_message = str(cli_error_from_repository_error(err))
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
    deadline_sources = {"deadline", "overdue_deadline", "upcoming_deadline", "deadline_today"}
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
    elif row.source in {"deadline", "deadline_today"}:
        timestamp = node.deadline
        field_name = "deadline"
    if timestamp is None:
        return None, "Time shifting is available only for timed scheduled/deadline rows"
    if not has_specific_time(timestamp):
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
    _save_document_changes(session, heading.document)
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
    _save_document_changes(session, heading.document)
    preserve_identity = heading_locator(heading)
    _reload_session_nodes(session)
    refresh_session(session, preserve_identity)
    session.status_message = status


def apply_shift_time(session: AgendaSession, *, hour_delta: int) -> None:
    """Shift the selected timed planning row by the requested hour delta."""
    row = selected_task_row(session)
    if row is None or row.node is None:
        session.status_message = "Action available only on task rows"
        return
    timestamp, status = shift_planning_time_for_row(row, hour_delta=hour_delta)
    if timestamp is None:
        session.status_message = status
        return
    heading = row.node
    _save_document_changes(session, heading.document)
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
    destination_path = destination_input.strip()
    if not destination_path:
        session.status_message = "Refile cancelled"
        return
    try:
        destination_document = session.repository.get_document(destination_path)
    except (RepositoryError, typer.BadParameter) as err:
        session.status_message = str(cli_error_from_repository_error(err))
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
    _save_document_changes(session, destination_document)
    if source_document is not destination_document:
        _save_document_changes(session, source_document)
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
    _save_document_changes(session, row.node.document)
    preserve_identity = heading_locator(row.node)
    _reload_session_nodes(session)
    refresh_session(session, preserve_identity)
    session.status_message = f"Added clock entry ({duration_text})"


def clear_search(session: AgendaSession) -> None:
    """Clear the active agenda search filter while preserving selection when possible."""
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
    location = selected_row_location(session)
    if location is None:
        return None
    day_index, row_index = location
    return session.day_models[day_index].rows[row_index]


def _timetable_schedule_for_selected_row(session: AgendaSession) -> Timestamp | None:
    row = selected_row(session)
    if row is None:
        return None
    if row.kind == "task" and row.source not in {
        "scheduled",
        "deadline",
        "deadline_today",
        "repeat",
    }:
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


def apply_capture_task(session: AgendaSession, template_name: str) -> None:
    """Capture a task from one template and schedule it for the selected timetable row."""
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
        capture_result = capture_task(capture_args, session.app_config.tasks.capture.templates)
    except KeyboardInterrupt:
        session.status_message = "Capture cancelled"
        return
    except typer.BadParameter as err:
        session.status_message = str(err)
        return
    capture_result.heading.scheduled = scheduled
    try:
        _save_document_changes(session, capture_result.document)
        _reload_session_nodes(session)
        refresh_session(session, heading_locator(capture_result.heading))
    except (RepositoryError, QueryParseError, QueryRuntimeError, typer.BadParameter) as err:
        session.status_message = str(cli_error_from_repository_error(err))
        return
    session.status_message = f"Task captured and scheduled for {scheduled}"


def state_choices_for_selected_row(session: AgendaSession) -> list[str]:
    """Return valid TODO state choices for the selected task row."""
    row = selected_task_row(session)
    if row is None or row.node is None:
        return []
    return todo_states_for_heading(row.node)


def _can_activate_agenda_state_prompt(session: AgendaSession) -> str | None:
    row = selected_task_row(session)
    if row is None or row.node is None:
        return "Action available only on task rows"
    if not state_choices_for_selected_row(session):
        return "No TODO states defined"
    return None


def can_activate_agenda_state_prompt(session: AgendaSession) -> str | None:
    """Return status text when the state prompt cannot be opened."""
    return _can_activate_agenda_state_prompt(session)


def can_activate_agenda_capture_prompt(session: AgendaSession) -> str | None:
    """Return status text when the capture prompt cannot be opened."""
    if _timetable_schedule_for_selected_row(session) is None:
        return "Capture is available only on timetable time rows"
    if not session.app_config.tasks.capture.templates:
        return "No capture templates configured"
    return None


def apply_search_text(session: AgendaSession, search_text: str) -> None:
    """Apply agenda search text and refresh the visible day models."""
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
    config: AppConfig,
    data: AgendaSessionData,
) -> AgendaSession:
    """Create interactive session state for agenda."""
    session = AgendaSession(
        args=args,
        all_nodes=list(data.nodes),
        nodes=data.nodes,
        render=data.render,
        start_date=resolve_agenda_start_date(args.date),
        days=args.days,
        now=local_now(),
        day_models=[],
        interactive_rows=[],
        column_widths=AgendaColumnWidths(category=8, time=10, tags=4),
        row_locations=[],
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
        search_text="",
        view_ctx=data.view_ctx,
        app_config=config,
        repository=data.repository,
    )
    refresh_session(session, None)
    return session


def set_start_date_relative(session: AgendaSession, *, day_delta: int) -> None:
    """Move the agenda start date relative to the current visible span."""
    session.start_date += timedelta(days=day_delta)
    refresh_session(session, None)


def passthrough_run_external(callback: Callable[[], None]) -> None:
    """Run an external callback immediately."""
    callback()


def _run_external(session: AgendaSession, callback: Callable[[], None]) -> None:
    runner = session.run_external or passthrough_run_external
    runner(callback)
