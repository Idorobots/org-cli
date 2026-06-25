"""Board interactive event handlers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, cast

import typer
from org_parser.document import Heading

import org.config.app
from org.commands.tasks.capture import TasksCaptureArgs, capture_task
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
from org.query.runner import build_filter_order_query_text, run_query


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from org_parser.document import Document

    from org.config.app import AppConfig, BoardViewConfig

    from .command import BoardArgs


logger = logging.getLogger("org")


def _board_query_error_builder(
    view_name: str,
    column_name: str,
) -> Callable[[str], typer.BadParameter]:
    """Build one board query runtime error converter."""

    def _query_error(message: str) -> typer.BadParameter:
        return typer.BadParameter(
            "Board filter/order-by query failed "
            f"(view={view_name}, column={column_name}): {message}",
        )

    return _query_error


@dataclass
class BoardColumn:
    """One board column with title and assigned tasks."""

    title: str
    nodes: list[Heading]


@dataclass(frozen=True)
class BoardColumnSpec:
    """One board column filter specification."""

    name: str
    view_name: str
    query_text: str


@dataclass
class BoardSession:
    """Interactive board session state."""

    args: BoardArgs
    nodes: list[Heading]
    todo_states: list[str]
    done_states: list[str]
    columns: Sequence[BoardColumn]
    color_enabled: bool
    selected_column_index: int
    selected_row_index: int
    scroll_offset: int
    status_message: str
    app_config: AppConfig
    repository: OrgRepository
    all_columns: Sequence[BoardColumn] = field(default_factory=list)
    search_text: str = ""


@dataclass(frozen=True)
class BoardSessionData:
    """Prepared board session inputs shared with the app layer."""

    repository: OrgRepository
    nodes: list[Heading]
    state_lists: tuple[list[str], list[str]]
    color_enabled: bool


def _coerce_latest_timestamp_start(node: Heading) -> datetime | None:
    """Return node latest timestamp start value when available."""
    latest_timestamp = node.latest_timestamp
    if latest_timestamp is None:
        return None
    return latest_timestamp.start


def filter_recent_completed_nodes(nodes: list[Heading], days: int) -> list[Heading]:
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


def resolved_states(
    args: BoardArgs,
    discovered_todo_states: list[str],
    discovered_done_states: list[str],
) -> tuple[list[str], list[str]]:
    """Resolve visible flow board states from configured and discovered states."""
    specified_todo_states, specified_done_states = _specified_states(args)
    todo_states = _restore_key_order(specified_todo_states, discovered_todo_states)
    done_states = _restore_key_order(specified_done_states, discovered_done_states)
    return todo_states, done_states


def _fallback_view_config() -> org.config.app.BoardViewConfig:
    """Return built-in fallback board filter view definition."""
    return org.config.app.BoardViewConfig(
        name="fallback",
        columns=[
            org.config.app.BoardColumnConfig(name="Backlog", filter=".todo == null"),
            org.config.app.BoardColumnConfig(
                name="TODO",
                filter=".todo != null and not(.is_completed)",
            ),
            org.config.app.BoardColumnConfig(name="DONE", filter=".is_completed"),
        ],
    )


def compile_view_column_specs(view: org.config.app.BoardViewConfig) -> list[BoardColumnSpec]:
    """Compile one board view's filters into renderable column specs."""
    column_specs: list[BoardColumnSpec] = []
    for column in view.columns:
        try:
            query_text = build_filter_order_query_text(column.filter, column.order_by)
            run_query([], [query_text], {})
        except (QueryParseError, QueryRuntimeError) as err:
            raise typer.BadParameter(
                f"Invalid board filter/order-by (view={view.name}, column={column.name}): {err}",
            ) from err
        column_specs.append(
            BoardColumnSpec(
                name=column.name,
                view_name=view.name,
                query_text=query_text,
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


def resolve_column_specs(
    args: BoardArgs,
    configured_views: dict[str, BoardViewConfig],
) -> list[BoardColumnSpec]:
    """Resolve configured or fallback filter columns for board rendering."""
    selected_view = _resolve_selected_view_name(args)
    if selected_view is None:
        return compile_view_column_specs(_fallback_view_config())

    if not configured_views:
        raise typer.BadParameter("--view requested, but no board views are configured")

    selected_view_config = configured_views.get(selected_view)
    if selected_view_config is None:
        raise typer.BadParameter(f"Requested board view not found: {selected_view}")

    return compile_view_column_specs(selected_view_config)


def build_selector_board_columns(
    nodes: list[Heading],
    column_specs: list[BoardColumnSpec],
) -> list[BoardColumn]:
    """Evaluate filter specs against processed task stream."""
    columns: list[BoardColumn] = []
    for spec in column_specs:
        try:
            results = run_query(nodes, [spec.query_text], {})
        except QueryParseError as exc:
            raise typer.BadParameter(
                f"Invalid board filter/order-by (view={spec.view_name}, column={spec.name}): {exc}",
            ) from exc
        except QueryRuntimeError as exc:
            raise _board_query_error_builder(spec.view_name, spec.name)(str(exc)) from exc

        column_nodes = [cast("Heading", node) for node in results]
        columns.append(BoardColumn(title=spec.name, nodes=column_nodes))

    return columns


def _max_column_nodes(columns: list[BoardColumn]) -> int:
    """Return maximum node count among board columns."""
    return max((len(column.nodes) for column in columns), default=0)


def _column_with_filtered_nodes(column: BoardColumn, search_text: str) -> BoardColumn:
    """Return one board column with nodes filtered by search text."""
    filtered_nodes = filter_nodes_by_search(column.nodes, search_text)
    return BoardColumn(title=column.title, nodes=filtered_nodes)


def _filter_columns_by_search(
    columns: Sequence[BoardColumn],
    search_text: str,
) -> list[BoardColumn]:
    """Filter nodes in each column by interactive search text."""
    return [_column_with_filtered_nodes(column, search_text) for column in columns]


def _visible_task_count(columns: Sequence[BoardColumn]) -> int:
    """Return total number of visible tasks across all board columns."""
    return sum(len(column.nodes) for column in columns)


def _ensure_selection_bounds(session: BoardSession) -> None:
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


def refresh_visible_columns(
    session: BoardSession,
    preserve_identity: HeadingLocator | None,
) -> None:
    """Refresh visible board columns and restore selected task when possible."""
    source_columns = session.all_columns or session.columns
    session.columns = _filter_columns_by_search(source_columns, session.search_text)

    visible_nodes = [node for column in session.columns for node in column.nodes]
    preserved_node = resolve_heading_locator(visible_nodes, preserve_identity)
    if preserved_node is not None:
        for column_index, column in enumerate(session.columns):
            for row_index, node in enumerate(column.nodes):
                if node is preserved_node:
                    session.selected_column_index = column_index
                    session.selected_row_index = row_index
                    _ensure_selection_bounds(session)
                    return

    _ensure_selection_bounds(session)


def selected_node(session: BoardSession) -> Heading | None:
    """Return selected task node, if current selection targets one."""
    if not session.columns:
        return None
    selected_nodes = session.columns[session.selected_column_index].nodes
    if not selected_nodes:
        return None
    if session.selected_row_index < 0 or session.selected_row_index >= len(selected_nodes):
        return None
    return selected_nodes[session.selected_row_index]


def reload_session(
    session: BoardSession,
    preserve_identity: HeadingLocator | None,
) -> None:
    """Reload processed nodes and rebuild board columns."""
    plan = build_repository_query_plan(session.args, session.app_config, include_ordering=True)
    results = session.repository.query(plan.stages, plan.context)
    nodes = [value for value in results if isinstance(value, Heading)]
    limit = session.args.max_results
    if limit is not None:
        nodes = nodes[session.args.offset : session.args.offset + limit]
    discovered_todo_states = session.repository.todo_states
    discovered_done_states = session.repository.done_states
    todo_states, done_states = resolved_states(
        session.args,
        discovered_todo_states,
        discovered_done_states,
    )

    filtered_nodes = filter_recent_completed_nodes(nodes, session.args.days)

    session.nodes = filtered_nodes
    session.todo_states = todo_states
    session.done_states = done_states
    session.all_columns = build_selector_board_columns(
        filtered_nodes,
        resolve_column_specs(session.args, session.app_config.board.views),
    )
    refresh_visible_columns(session, preserve_identity)


def create_board_session(
    args: BoardArgs,
    config: AppConfig,
    data: BoardSessionData,
) -> BoardSession:
    """Create interactive board session state."""
    todo_states, done_states = data.state_lists
    columns = build_selector_board_columns(
        data.nodes,
        resolve_column_specs(args, config.board.views),
    )
    selected_column_index = 0
    for index, column in enumerate(columns):
        if column.nodes:
            selected_column_index = index
            break

    session = BoardSession(
        args=args,
        nodes=data.nodes,
        todo_states=todo_states,
        done_states=done_states,
        app_config=config,
        repository=data.repository,
        all_columns=columns,
        columns=columns,
        color_enabled=data.color_enabled,
        selected_column_index=selected_column_index,
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
        search_text="",
    )
    _ensure_selection_bounds(session)
    return session


def _save_document_changes(session: BoardSession, document: Document) -> None:
    """Persist one mutated document to disk."""
    logger.info("Saving flow board edit file: %s", document.filename)
    session.repository.save_document(document.filename or "")


def step_heading_state(heading: Heading, *, direction: int) -> tuple[str | None, str | None]:
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


def move_selection_vertical(session: BoardSession, step: int) -> None:
    """Move highlighted task up/down in the selected column."""
    selected_nodes = session.columns[session.selected_column_index].nodes
    if not selected_nodes:
        session.status_message = "Selected column has no tasks"
        return

    next_index = session.selected_row_index + step
    session.selected_row_index = min(max(next_index, 0), len(selected_nodes) - 1)


def move_selection_horizontal(session: BoardSession, step: int) -> None:
    """Move highlighted lane left/right, skipping empty columns."""
    next_column = session.selected_column_index + step
    while 0 <= next_column < len(session.columns):
        selected_nodes = session.columns[next_column].nodes
        if selected_nodes:
            session.selected_column_index = next_column
            session.selected_row_index = min(session.selected_row_index, len(selected_nodes) - 1)
            return
        next_column += step


def apply_state_move(session: BoardSession, *, direction: int) -> None:
    """Step selected task state through document state ordering."""
    heading = selected_node(session)
    if heading is None:
        session.status_message = "Action available only on task panels"
        return

    new_state, status = step_heading_state(heading, direction=direction)
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

    _save_document_changes(session, heading.document)
    preserve_identity = heading_locator(heading)
    try:
        reload_session(session, preserve_identity)
    except (RepositoryError, QueryParseError, QueryRuntimeError, typer.BadParameter) as err:
        session.status_message = str(cli_error_from_repository_error(err))
        return
    session.status_message = f"State updated: {old_state or '-'} -> {new_state or '-'}"


def apply_priority_shift(session: BoardSession, *, increase: bool) -> None:
    """Increase or decrease selected task priority."""
    heading = selected_node(session)
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
    _save_document_changes(session, heading.document)
    preserve_identity = heading_locator(heading)
    try:
        reload_session(session, preserve_identity)
    except (RepositoryError, QueryParseError, QueryRuntimeError, typer.BadParameter) as err:
        session.status_message = str(cli_error_from_repository_error(err))
        return
    session.status_message = f"Priority updated: {old_priority or '-'} -> {new_priority or '-'}"


def edit_selected_task_in_external_editor(session: BoardSession) -> None:
    """Edit selected task subtree in configured external editor."""
    heading = selected_node(session)
    if heading is None:
        session.status_message = "Action available only on task panels"
        return

    preserve_identity = heading_locator(heading)
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
        reload_session(session, preserve_identity)
    except typer.BadParameter as err:
        session.status_message = str(err)
        return
    session.status_message = "Task updated"


def archive_selected_task(session: BoardSession) -> None:
    """Archive selected task subtree using shared archive-location rules."""
    heading = selected_node(session)
    if heading is None:
        session.status_message = "Action available only on task panels"
        return

    session.status_message = ""
    try:
        archive_result = archive_heading_subtree_and_save(heading, {}, session.repository)
    except (RepositoryError, typer.BadParameter) as err:
        session.status_message = str(cli_error_from_repository_error(err))
        return

    preserve_identity = heading_locator(archive_result.heading)
    try:
        reload_session(session, preserve_identity)
    except (RepositoryError, QueryParseError, QueryRuntimeError, typer.BadParameter) as err:
        session.status_message = str(cli_error_from_repository_error(err))
        return
    session.status_message = "Task archived"


def apply_capture_task(session: BoardSession, template_name: str) -> None:
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
        capture_result = capture_task(capture_args, session.app_config.tasks.capture.templates)
    except KeyboardInterrupt:
        session.status_message = "Capture cancelled"
        return
    except typer.BadParameter as err:
        session.status_message = str(err)
        return

    try:
        reload_session(session, heading_locator(capture_result.heading))
    except (RepositoryError, QueryParseError, QueryRuntimeError, typer.BadParameter) as err:
        session.status_message = str(cli_error_from_repository_error(err))
        return
    session.status_message = "Task captured"


def clear_search(session: BoardSession) -> None:
    """Clear active interactive search and restore full board columns."""
    if not session.search_text:
        session.status_message = "Search already clear"
        return

    selected = selected_node(session)
    preserve_identity = heading_locator(selected) if selected is not None else None
    session.search_text = ""
    refresh_visible_columns(session, preserve_identity)
    session.status_message = "Search cleared"


def apply_search_text(session: BoardSession, search_text: str) -> None:
    """Apply search text to board columns and update match status."""
    selected = selected_node(session)
    preserve_identity = heading_locator(selected) if selected is not None else None
    session.search_text = search_text
    refresh_visible_columns(session, preserve_identity)
    session.status_message = (
        "Search cleared" if not search_text else f"{_visible_task_count(session.columns)} matches"
    )


def can_activate_capture_prompt(session: BoardSession) -> str | None:
    """Return status text when the capture prompt cannot be opened."""
    if not session.app_config.tasks.capture.templates:
        return "No capture templates configured"
    return None
