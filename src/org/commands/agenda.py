"""Agenda command for day-based task planning views."""

from __future__ import annotations

import calendar
import logging
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from org_parser.time import Clock, Timestamp
from rich import box
from rich.console import Group
from rich.live import Live
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from org import config as config_module
from org.cli_common import load_and_process_data, resolve_input_paths
from org.commands.archive import archive_heading_subtree_and_save
from org.commands.editor import edit_heading_subtree_in_external_editor
from org.commands.interactive_common import (
    KeyBinding,
    append_repeat_transition,
    dispatch_key_binding,
    key_binding_for_action,
    key_binding_requires_live_pause,
    local_now,
    read_keypress,
    set_mouse_reporting,
)
from org.commands.tasks.common import iter_descendants, load_document, save_document
from org.tui import (
    build_console,
    heading_title_to_text,
    processing_status,
    setup_output,
    task_priority_to_text,
    task_state_prefix_to_text,
    task_tags_to_text,
)
from org.validation import parse_date_argument


if TYPE_CHECKING:
    from org_parser.document import Document, Heading
    from rich.console import Console


logger = logging.getLogger("org")
_HIGHLIGHT_ROW_STYLE = "on grey23"


@dataclass
class AgendaArgs:
    """Arguments for the agenda command."""

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
    offset: int
    order_by_level: bool
    order_by_file_order: bool
    order_by_file_order_reversed: bool
    order_by_priority: bool
    order_by_timestamp_asc: bool
    order_by_timestamp_desc: bool
    with_tags_as_category: bool
    date: str | None
    days: int
    no_completed: bool
    no_overdue: bool
    no_upcoming: bool


@dataclass(frozen=True)
class _TimedEntry:
    """One timed agenda entry."""

    node: Heading
    when: datetime
    kind: str
    state_override: str | None = None


@dataclass(frozen=True)
class _RelativeEntry:
    """One relative-date agenda entry."""

    node: Heading
    delta_days: int


@dataclass(frozen=True)
class _DayEntries:
    """Per-day grouped agenda entries."""

    timed: list[_TimedEntry]
    overdue_scheduled: list[_RelativeEntry]
    overdue_deadline: list[_RelativeEntry]
    deadline_untimed: list[Heading]
    scheduled_untimed: list[Heading]
    upcoming_deadline: list[_RelativeEntry]


@dataclass(frozen=True)
class _RenderContext:
    """Shared rendering context for agenda rows."""

    color_enabled: bool
    done_states: list[str]
    todo_states: list[str]


@dataclass(frozen=True)
class _TaskRow:
    """Renderable task row data."""

    node: Heading
    time_text: str
    style: str = ""
    prefix: str | None = None
    state_override: str | None = None


@dataclass(frozen=True)
class _DayRenderInput:
    """Per-day rendering input for agenda rows."""

    day: date
    now: datetime
    entries: _DayEntries


@dataclass(frozen=True)
class _RelativeSectionInput:
    """Renderable input for one relative section."""

    label: str
    entries: list[_RelativeEntry]
    style: str
    direction: str
    prefix: str | None = None


@dataclass(frozen=True)
class _AgendaRenderInput:
    """Top-level agenda rendering input."""

    args: AgendaArgs
    nodes: list[Heading]
    now: datetime
    render: _RenderContext


@dataclass(frozen=True)
class _AgendaRow:
    """One renderable agenda row, optionally bound to a task."""

    kind: str
    day: date
    time_text: str = ""
    section_label: str = ""
    node: Heading | None = None
    source: str = ""
    style: str = ""
    prefix: str | None = None
    state_override: str | None = None


@dataclass
class _DayRowModel:
    """Rows and selectable row indexes for one day."""

    day: date
    rows: list[_AgendaRow]
    selectable_row_indexes: list[int]


@dataclass
class _AgendaSession:
    """Interactive agenda session state."""

    args: AgendaArgs
    nodes: list[Heading]
    render: _RenderContext
    start_date: date
    days: int
    now: datetime
    day_models: list[_DayRowModel]
    row_locations: list[tuple[int, int]]
    selected_row_index: int
    scroll_offset: int
    status_message: str


@dataclass(frozen=True)
class _ViewportRow:
    """One interactive viewport row with optional bound agenda row."""

    kind: str
    day: date
    agenda_row: _AgendaRow | None
    location: tuple[int, int] | None


@dataclass(frozen=True)
class _RelativeRowsSpec:
    """Specification for building one relative section row group."""

    label: str
    entries: list[_RelativeEntry]
    source: str
    style: str
    in_future: bool
    prefix: str | None = None


def _has_specific_time(timestamp: Timestamp) -> bool:
    """Return whether an org timestamp includes an explicit start time."""
    return timestamp.start_hour is not None


def _is_active_planning_timestamp(timestamp: Timestamp | None) -> bool:
    """Return whether a planning timestamp is present and active."""
    return bool(timestamp is not None and timestamp.is_active)


def _resolve_agenda_start_date(raw_date: str | None) -> date:
    """Resolve agenda start date from --date or today's date."""
    if raw_date is None:
        return local_now().date()
    return parse_date_argument(raw_date, "--date").date()


def _resolve_tasks_limit(max_results: int | None) -> int:
    """Resolve effective tasks limit, defaulting to all available tasks."""
    if max_results is None:
        return sys.maxsize
    return max_results


def _format_relative_days(delta_days: int, *, in_future: bool) -> str:
    """Format relative day offset for agenda time column."""
    if in_future:
        return f"in {delta_days}d"
    return f"{delta_days}d ago"


def _category_text(node: Heading) -> Text:
    """Build category text cell for one heading."""
    category = node.category
    if category is None or str(category).strip() == "":
        return Text("-")
    return Text(str(category))


def _tags_text(node: Heading, color_enabled: bool) -> Text:
    """Build tags text cell for one heading."""
    return task_tags_to_text(node.tags, color_enabled)


def _heading_text(
    node: Heading,
    *,
    render: _RenderContext,
    prefix: str | None = None,
    state_override: str | None = None,
) -> Text:
    """Build heading cell text with state, priority, and rich title."""
    heading = Text()
    if prefix:
        heading.append(prefix, style="dim" if render.color_enabled else "")

    state = state_override if state_override is not None else (node.todo or "")
    if state:
        heading.append_text(
            task_state_prefix_to_text(
                state,
                done_states=render.done_states,
                todo_states=render.todo_states,
                color_enabled=render.color_enabled,
            ),
        )

    heading.append_text(
        task_priority_to_text(
            node.priority,
            render.color_enabled,
            trailing_space=True,
        ),
    )

    heading.append_text(heading_title_to_text(node))
    return heading


def _scheduled_for_day(node: Heading, day: date) -> bool:
    """Return whether heading is scheduled for the given day."""
    return bool(
        node.scheduled
        and _is_active_planning_timestamp(node.scheduled)
        and node.scheduled.start.date() == day,
    )


def _collect_repeat_timed_entries(
    node: Heading,
    day: date,
    *,
    no_completed: bool,
) -> list[_TimedEntry]:
    """Collect completed repeat entries for one day."""
    timed: list[_TimedEntry] = []
    if no_completed:
        return timed

    repeats = [repeat for repeat in node.repeats if repeat.is_completed]
    for repeat in repeats:
        repeat_day = repeat.timestamp.start.date()
        if repeat_day != day:
            continue
        if _has_specific_time(repeat.timestamp):
            timed.append(
                _TimedEntry(
                    node=node,
                    when=repeat.timestamp.start,
                    kind="repeat",
                    state_override=repeat.after,
                ),
            )
    return timed


def _collect_scheduled_entries(node: Heading, day: date) -> tuple[list[_TimedEntry], list[Heading]]:
    """Collect scheduled entries on one day."""
    timed: list[_TimedEntry] = []
    untimed: list[Heading] = []
    if not _scheduled_for_day(node, day) or node.scheduled is None:
        return timed, untimed

    if _has_specific_time(node.scheduled):
        timed.append(_TimedEntry(node=node, when=node.scheduled.start, kind="scheduled"))
    else:
        untimed.append(node)
    return timed, untimed


def _collect_deadline_entries(
    node: Heading,
    day: date,
    *,
    completed: bool,
) -> tuple[list[_TimedEntry], list[Heading]]:
    """Collect deadline entries on one day for incomplete tasks."""
    timed: list[_TimedEntry] = []
    untimed: list[Heading] = []
    if completed or not _is_active_planning_timestamp(node.deadline) or node.deadline is None:
        return timed, untimed
    if node.deadline.start.date() != day:
        return timed, untimed

    if _has_specific_time(node.deadline):
        timed.append(_TimedEntry(node=node, when=node.deadline.start, kind="deadline"))
    else:
        untimed.append(node)
    return timed, untimed


def _overdue_scheduled_entry(
    node: Heading,
    day: date,
    *,
    completed: bool,
    no_overdue: bool,
) -> _RelativeEntry | None:
    """Return overdue scheduled entry when applicable."""
    if completed or no_overdue or not _is_active_planning_timestamp(node.scheduled):
        return None
    if node.scheduled is None:
        return None
    scheduled_day = node.scheduled.start.date()
    if scheduled_day >= day:
        return None
    return _RelativeEntry(node=node, delta_days=(day - scheduled_day).days)


def _overdue_deadline_entry(
    node: Heading,
    day: date,
    *,
    completed: bool,
    no_overdue: bool,
) -> _RelativeEntry | None:
    """Return overdue deadline entry when applicable."""
    if completed or no_overdue or not _is_active_planning_timestamp(node.deadline):
        return None
    if node.deadline is None:
        return None
    deadline_day = node.deadline.start.date()
    if deadline_day >= day:
        return None
    return _RelativeEntry(node=node, delta_days=(day - deadline_day).days)


def _upcoming_deadline_entry(
    node: Heading,
    day: date,
    upcoming_limit: date,
    *,
    completed: bool,
    no_upcoming: bool,
) -> _RelativeEntry | None:
    """Return upcoming deadline entry when applicable."""
    if completed or no_upcoming or not _is_active_planning_timestamp(node.deadline):
        return None
    if node.deadline is None:
        return None
    deadline_day = node.deadline.start.date()
    if not (day < deadline_day <= upcoming_limit):
        return None
    return _RelativeEntry(node=node, delta_days=(deadline_day - day).days)


def _collect_day_entries(
    nodes: list[Heading],
    day: date,
    args: AgendaArgs,
    *,
    include_relative_sections: bool,
) -> _DayEntries:
    """Collect and group agenda entries for one day."""
    timed: list[_TimedEntry] = []
    overdue_scheduled: list[_RelativeEntry] = []
    overdue_deadline: list[_RelativeEntry] = []
    deadline_untimed: list[Heading] = []
    scheduled_untimed: list[Heading] = []
    upcoming_deadline: list[_RelativeEntry] = []
    deadline_untimed_identity: set[tuple[str, int | None, str]] = set()

    upcoming_limit = day + timedelta(days=30)

    for node in nodes:
        completed = node.is_completed
        if args.no_completed and completed:
            continue

        scheduled_timed, scheduled_day_untimed = _collect_scheduled_entries(node, day)
        timed.extend(scheduled_timed)
        if not completed:
            scheduled_untimed.extend(scheduled_day_untimed)

        deadline_timed, deadline_day_untimed = _collect_deadline_entries(
            node,
            day,
            completed=completed,
        )
        timed.extend(deadline_timed)
        for deadline_node in deadline_day_untimed:
            deadline_untimed.append(deadline_node)
            deadline_untimed_identity.add(
                (
                    deadline_node.document.filename or "",
                    deadline_node.line,
                    deadline_node.title_text,
                ),
            )

        repeat_timed = _collect_repeat_timed_entries(
            node,
            day,
            no_completed=args.no_completed,
        )
        timed.extend(repeat_timed)

        if include_relative_sections:
            overdue_scheduled_entry = _overdue_scheduled_entry(
                node,
                day,
                completed=completed,
                no_overdue=args.no_overdue,
            )
            if overdue_scheduled_entry is not None:
                overdue_scheduled.append(overdue_scheduled_entry)

            overdue_deadline_entry = _overdue_deadline_entry(
                node,
                day,
                completed=completed,
                no_overdue=args.no_overdue,
            )
            if overdue_deadline_entry is not None:
                overdue_deadline.append(overdue_deadline_entry)

            upcoming_deadline_entry = _upcoming_deadline_entry(
                node,
                day,
                upcoming_limit,
                completed=completed,
                no_upcoming=args.no_upcoming,
            )
            if upcoming_deadline_entry is not None:
                upcoming_deadline.append(upcoming_deadline_entry)

    timed.sort(key=lambda entry: entry.when)
    overdue_scheduled.sort(key=lambda entry: (-entry.delta_days, str(entry.node.title_text)))
    overdue_deadline.sort(key=lambda entry: (-entry.delta_days, str(entry.node.title_text)))
    upcoming_deadline.sort(key=lambda entry: (entry.delta_days, str(entry.node.title_text)))
    scheduled_untimed = [
        node
        for node in scheduled_untimed
        if (node.document.filename or "", node.line, node.title_text)
        not in deadline_untimed_identity
    ]
    return _DayEntries(
        timed=timed,
        overdue_scheduled=overdue_scheduled,
        overdue_deadline=overdue_deadline,
        deadline_untimed=deadline_untimed,
        scheduled_untimed=scheduled_untimed,
        upcoming_deadline=upcoming_deadline,
    )


def _merge_row_style(base_style: str, *, highlighted: bool) -> str:
    """Merge base row style with highlight style."""
    if not highlighted:
        return base_style
    if base_style:
        return f"{base_style} {_HIGHLIGHT_ROW_STYLE}"
    return _HIGHLIGHT_ROW_STYLE


def _row_for_timed_entry(entry: _TimedEntry, day: date) -> _AgendaRow:
    """Build one row model for a timed entry."""
    source_map = {
        "repeat": "repeat",
        "scheduled": "scheduled",
        "deadline": "deadline_today",
    }
    source = source_map.get(entry.kind, "scheduled")
    return _AgendaRow(
        kind="task",
        day=day,
        time_text=entry.when.strftime("%H:%M"),
        node=entry.node,
        source=source,
        state_override=entry.state_override,
    )


def _build_hour_rows(day_render: _DayRenderInput) -> list[_AgendaRow]:
    """Build timetable hour, now-marker, and timed task rows for one day."""
    rows: list[_AgendaRow] = []
    timed_by_hour: dict[int, list[_TimedEntry]] = {hour: [] for hour in range(24)}
    for entry in day_render.entries.timed:
        timed_by_hour[entry.when.hour].append(entry)

    for hour in range(24):
        rows.append(
            _AgendaRow(
                kind="hour_marker",
                day=day_render.day,
                time_text=f"{hour:02d}:00",
            ),
        )

        hour_entries = timed_by_hour[hour]
        is_now_hour = day_render.day == day_render.now.date() and day_render.now.hour == hour
        now_inserted = False
        for timed_entry in hour_entries:
            if is_now_hour and not now_inserted and timed_entry.when.minute > day_render.now.minute:
                rows.append(
                    _AgendaRow(
                        kind="now_marker",
                        day=day_render.day,
                        time_text=day_render.now.strftime("%H:%M"),
                    ),
                )
                now_inserted = True
            rows.append(_row_for_timed_entry(timed_entry, day_render.day))

        if is_now_hour and not now_inserted:
            rows.append(
                _AgendaRow(
                    kind="now_marker",
                    day=day_render.day,
                    time_text=day_render.now.strftime("%H:%M"),
                ),
            )
    return rows


def _relative_section_rows(
    day: date,
    spec: _RelativeRowsSpec,
) -> list[_AgendaRow]:
    """Build rows for one overdue/upcoming relative section."""
    if not spec.entries:
        return []

    rows = [_AgendaRow(kind="section", day=day, section_label=spec.label, style=spec.style)]
    rows.extend(
        _AgendaRow(
            kind="task",
            day=day,
            time_text=_format_relative_days(entry.delta_days, in_future=spec.in_future),
            node=entry.node,
            source=spec.source,
            style=spec.style,
            prefix=spec.prefix,
        )
        for entry in spec.entries
    )
    return rows


def _scheduled_untimed_rows(day: date, entries: list[Heading]) -> list[_AgendaRow]:
    """Build rows for scheduled-without-time section."""
    if not entries:
        return []

    rows = [_AgendaRow(kind="section", day=day, section_label="Scheduled without specific time")]
    rows.extend(
        _AgendaRow(
            kind="task",
            day=day,
            node=node,
            source="scheduled_untimed",
        )
        for node in entries
    )
    return rows


def _deadline_untimed_rows(day: date, entries: list[Heading]) -> list[_AgendaRow]:
    """Build rows for deadline-without-time section."""
    if not entries:
        return []

    rows = [_AgendaRow(kind="section", day=day, section_label="Deadlines without specific time")]
    rows.extend(
        _AgendaRow(
            kind="task",
            day=day,
            node=node,
            source="deadline_today",
        )
        for node in entries
    )
    return rows


def _build_day_rows(day_render: _DayRenderInput, render: _RenderContext) -> _DayRowModel:
    """Build all render rows and selectable indexes for one day."""
    rows: list[_AgendaRow] = []
    rows.extend(_build_hour_rows(day_render))
    rows.extend(
        _relative_section_rows(
            day_render.day,
            _RelativeRowsSpec(
                label="Overdue deadlines",
                entries=day_render.entries.overdue_deadline,
                source="overdue_deadline",
                style="bold red" if render.color_enabled else "",
                in_future=False,
            ),
        ),
    )
    rows.extend(
        _relative_section_rows(
            day_render.day,
            _RelativeRowsSpec(
                label="Overdue scheduled",
                entries=day_render.entries.overdue_scheduled,
                source="overdue_scheduled",
                style="orange3" if render.color_enabled else "",
                in_future=False,
            ),
        ),
    )
    rows.extend(_deadline_untimed_rows(day_render.day, day_render.entries.deadline_untimed))
    rows.extend(_scheduled_untimed_rows(day_render.day, day_render.entries.scheduled_untimed))
    rows.extend(
        _relative_section_rows(
            day_render.day,
            _RelativeRowsSpec(
                label="Upcoming deadlines (30d)",
                entries=day_render.entries.upcoming_deadline,
                source="upcoming_deadline",
                style="yellow" if render.color_enabled else "",
                in_future=True,
            ),
        ),
    )

    selectable = [
        idx for idx, row in enumerate(rows) if row.kind == "task" and row.node is not None
    ]
    return _DayRowModel(day=day_render.day, rows=rows, selectable_row_indexes=selectable)


def _heading_identity(node: Heading) -> tuple[str, str, str, int | None]:
    """Build stable heading identity tuple for selection restoration."""
    filename = node.document.filename or ""
    heading_id = node.id or ""
    title = node.title_text
    return (filename, heading_id, title, node.line)


def _refresh_session(
    session: _AgendaSession,
    preserve_identity: tuple[str, str, str, int | None] | None,
) -> None:
    """Recompute day row models and restore selection when possible."""
    session.now = local_now()
    day_models: list[_DayRowModel] = []
    row_locations: list[tuple[int, int]] = []

    for day_offset in range(session.days):
        day = session.start_date + timedelta(days=day_offset)
        entries = _collect_day_entries(
            session.nodes,
            day,
            session.args,
            include_relative_sections=(day == session.now.date()),
        )
        day_model = _build_day_rows(
            _DayRenderInput(day=day, now=session.now, entries=entries),
            session.render,
        )
        day_models.append(day_model)
        row_locations.extend(
            (len(day_models) - 1, row_index) for row_index in range(len(day_model.rows))
        )

    session.day_models = day_models
    session.row_locations = row_locations

    if not row_locations:
        session.selected_row_index = 0
        return

    if preserve_identity is not None:
        for idx, (day_index, row_index) in enumerate(row_locations):
            row = day_models[day_index].rows[row_index]
            if row.node is not None and _heading_identity(row.node) == preserve_identity:
                session.selected_row_index = idx
                return

    if session.selected_row_index >= len(row_locations):
        session.selected_row_index = len(row_locations) - 1
    session.selected_row_index = max(session.selected_row_index, 0)


def _selected_row_location(session: _AgendaSession) -> tuple[int, int] | None:
    """Return selected day/row indexes or None when no rows exist."""
    if not session.row_locations:
        return None
    return session.row_locations[session.selected_row_index]


def _selected_task_row(session: _AgendaSession) -> _AgendaRow | None:
    """Return currently selected task row when selected row is a task."""
    location = _selected_row_location(session)
    if location is None:
        return None
    day_index, row_index = location
    row = session.day_models[day_index].rows[row_index]
    if row.kind != "task" or row.node is None:
        return None
    return row


def _refresh_session_if_minute_changed(session: _AgendaSession) -> None:
    """Refresh agenda rows when local wall-clock minute changes."""
    current_now = local_now().replace(second=0, microsecond=0)
    session_now = session.now.replace(second=0, microsecond=0)
    if current_now == session_now:
        return

    preserve_identity: tuple[str, str, str, int | None] | None = None
    selected_row = _selected_task_row(session)
    if selected_row is not None and selected_row.node is not None:
        preserve_identity = _heading_identity(selected_row.node)
    _refresh_session(session, preserve_identity)


def _paths_refer_to_same_file(source_path: str, destination_path: str) -> bool:
    """Return whether two path strings point to the same file."""
    try:
        source_resolved = Path(source_path).expanduser().resolve(strict=False)
        destination_resolved = Path(destination_path).expanduser().resolve(strict=False)
    except OSError:
        source_resolved = Path(source_path).expanduser().absolute()
        destination_resolved = Path(destination_path).expanduser().absolute()
    return source_resolved == destination_resolved


def _move_selection(session: _AgendaSession, step: int) -> None:
    """Move highlighted row selection forward/backward with wraparound."""
    if not session.row_locations:
        return
    session.selected_row_index = (session.selected_row_index + step) % len(session.row_locations)


def _set_timestamp_fields(timestamp: Timestamp, start: datetime, end: datetime | None) -> None:
    """Set timestamp date/time fields while preserving active/repeater metadata."""
    timestamp.start_year = start.year
    timestamp.start_month = start.month
    timestamp.start_day = start.day
    timestamp.start_dayname = start.strftime("%a")
    if timestamp.start_hour is not None:
        timestamp.start_hour = start.hour
        timestamp.start_minute = start.minute

    if end is None or timestamp.end is None:
        return

    timestamp.end_year = end.year
    timestamp.end_month = end.month
    timestamp.end_day = end.day
    timestamp.end_dayname = end.strftime("%a")
    if timestamp.end_hour is not None:
        timestamp.end_hour = end.hour
        timestamp.end_minute = end.minute


def _add_months(value: datetime, months: int) -> datetime:
    """Add months to a datetime while clamping day to month length."""
    year = value.year + (value.month - 1 + months) // 12
    month = (value.month - 1 + months) % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _shift_timestamp_by_days(timestamp: Timestamp, day_delta: int) -> None:
    """Shift one timestamp by a day delta."""
    shifted_start = timestamp.start + timedelta(days=day_delta)
    shifted_end = None if timestamp.end is None else timestamp.end + timedelta(days=day_delta)
    _set_timestamp_fields(timestamp, shifted_start, shifted_end)


def _shift_timestamp_by_hours(timestamp: Timestamp, hour_delta: int) -> None:
    """Shift one timestamp by an hour delta."""
    shifted_start = timestamp.start + timedelta(hours=hour_delta)
    shifted_end = None if timestamp.end is None else timestamp.end + timedelta(hours=hour_delta)
    _set_timestamp_fields(timestamp, shifted_start, shifted_end)


def _shift_datetimes_by_unit(
    start: datetime,
    end: datetime | None,
    *,
    value: int,
    unit: str,
) -> tuple[datetime, datetime | None]:
    """Shift start/end datetimes by one repeater unit."""
    if unit == "d":
        delta = timedelta(days=value)
        return start + delta, None if end is None else end + delta
    if unit == "w":
        delta = timedelta(weeks=value)
        return start + delta, None if end is None else end + delta
    if unit == "h":
        delta = timedelta(hours=value)
        return start + delta, None if end is None else end + delta
    if unit == "m":
        return _add_months(start, value), None if end is None else _add_months(end, value)
    if unit == "y":
        months = value * 12
        return _add_months(start, months), None if end is None else _add_months(end, months)
    raise ValueError(f"Unsupported repeater unit: {unit}")


def _now_aligned_for_datetime(start: datetime, now: datetime) -> datetime:
    """Normalize current datetime to match timezone-awareness of start."""
    if start.tzinfo is None:
        return now.replace(tzinfo=None)
    if now.tzinfo is None:
        return now.replace(tzinfo=start.tzinfo)
    return now.astimezone(start.tzinfo)


def _advance_timestamp_by_repeater(timestamp: Timestamp) -> bool:
    """Advance timestamp once by its repeater marker, when present."""
    if (
        timestamp.repeater_mark is None
        or timestamp.repeater_value is None
        or timestamp.repeater_unit is None
    ):
        return False

    mark = timestamp.repeater_mark
    value = timestamp.repeater_value
    unit = timestamp.repeater_unit
    if value <= 0:
        return False

    start = timestamp.start
    end = timestamp.end

    try:
        if mark == "+":
            shifted_start, shifted_end = _shift_datetimes_by_unit(
                start,
                end,
                value=value,
                unit=unit,
            )
        elif mark == "++":
            now = _now_aligned_for_datetime(start, local_now())
            shifted_start, shifted_end = _shift_datetimes_by_unit(
                start,
                end,
                value=value,
                unit=unit,
            )
            while shifted_start <= now:
                shifted_start, shifted_end = _shift_datetimes_by_unit(
                    shifted_start,
                    shifted_end,
                    value=value,
                    unit=unit,
                )
        elif mark == ".+":
            now = _now_aligned_for_datetime(start, local_now())
            base_start = start.replace(year=now.year, month=now.month, day=now.day)
            base_end = None if end is None else base_start + (end - start)
            shifted_start, shifted_end = _shift_datetimes_by_unit(
                base_start,
                base_end,
                value=value,
                unit=unit,
            )
        else:
            return False
    except ValueError:
        return False

    _set_timestamp_fields(timestamp, shifted_start, shifted_end)
    return True


def _save_document_changes(document: Document) -> None:
    """Persist one mutated document to disk."""
    logger.info("Saving agenda edit file: %s", document.filename)
    save_document(document)


def _parse_clock_duration(value: str) -> timedelta:
    """Parse user-entered clock duration text."""
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("Duration cannot be empty")

    if ":" in normalized:
        parts = normalized.split(":", 1)
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
            raise ValueError("Duration must be H:MM")
        hours = int(parts[0])
        minutes = int(parts[1])
        if minutes >= 60:
            raise ValueError("Minutes must be below 60")
        delta = timedelta(hours=hours, minutes=minutes)
    elif normalized.endswith("m") and normalized[:-1].isdigit():
        delta = timedelta(minutes=int(normalized[:-1]))
    elif normalized.endswith("h") and normalized[:-1].isdigit():
        delta = timedelta(hours=int(normalized[:-1]))
    elif normalized.isdigit():
        delta = timedelta(minutes=int(normalized))
    else:
        raise ValueError("Duration must be H:MM, Xm, Xh, or minutes")

    if delta <= timedelta(0):
        raise ValueError("Duration must be positive")
    return delta


def _duration_to_org_text(duration: timedelta) -> str:
    """Format duration as Org clock text H:MM."""
    total_minutes = int(duration.total_seconds() // 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}:{minutes:02d}"


def _reload_session_nodes(session: _AgendaSession) -> None:
    """Reload nodes through standard processing pipeline after mutations."""
    nodes, _, _ = load_and_process_data(session.args)
    session.nodes = nodes


def _add_section_row(table: Table, label: str, *, color_enabled: bool, style: str = "") -> int:
    """Add one section marker row to the agenda table."""
    heading = Text(label, style="bold" if color_enabled else "")
    table.add_row(Text(""), Text(""), heading, Text(""), style=style)
    return 1


def _add_task_row(table: Table, row: _TaskRow, render: _RenderContext) -> int:
    """Add one task row to the agenda table."""
    table.add_row(
        _category_text(row.node),
        Text(row.time_text),
        _heading_text(
            row.node,
            render=render,
            prefix=row.prefix,
            state_override=row.state_override,
        ),
        _tags_text(row.node, render.color_enabled),
        style=row.style,
    )
    return 1


def _render_hour_rows(table: Table, day_render: _DayRenderInput, render: _RenderContext) -> int:
    """Render 24-hour timetable rows with timed entries."""
    row_count = 0
    timed_by_hour: dict[int, list[_TimedEntry]] = {hour: [] for hour in range(24)}
    for entry in day_render.entries.timed:
        timed_by_hour[entry.when.hour].append(entry)

    for hour in range(24):
        hour_label = f"{hour:02d}:00"
        table.add_row(Text(""), Text(hour_label), Text("---------------", style="dim"), Text(""))
        row_count += 1

        hour_entries = timed_by_hour[hour]
        is_now_hour = day_render.day == day_render.now.date() and day_render.now.hour == hour
        now_inserted = False

        for timed_entry in hour_entries:
            if is_now_hour and not now_inserted and timed_entry.when.minute > day_render.now.minute:
                table.add_row(
                    Text(""),
                    Text(day_render.now.strftime("%H:%M")),
                    Text("------ NOW ------", style="bold yellow" if render.color_enabled else ""),
                    Text(""),
                )
                row_count += 1
                now_inserted = True

            row_count += _add_task_row(
                table,
                _TaskRow(
                    node=timed_entry.node,
                    time_text=timed_entry.when.strftime("%H:%M"),
                    state_override=timed_entry.state_override,
                ),
                render,
            )

        if is_now_hour and not now_inserted:
            table.add_row(
                Text(""),
                Text(day_render.now.strftime("%H:%M")),
                Text("------ NOW ------", style="bold yellow" if render.color_enabled else ""),
                Text(""),
            )
            row_count += 1

    return row_count


def _render_relative_section(
    table: Table,
    section: _RelativeSectionInput,
    render: _RenderContext,
) -> int:
    """Render one relative-date section and return rows added."""
    if not section.entries:
        return 0

    row_count = _add_section_row(
        table,
        section.label,
        color_enabled=render.color_enabled,
        style=section.style,
    )
    for entry in section.entries:
        in_future = section.direction == "future"
        row_count += _add_task_row(
            table,
            _TaskRow(
                node=entry.node,
                time_text=_format_relative_days(entry.delta_days, in_future=in_future),
                style=section.style,
                prefix=section.prefix,
            ),
            render,
        )
    return row_count


def _render_scheduled_untimed_section(
    table: Table,
    entries: list[Heading],
    render: _RenderContext,
) -> int:
    """Render the scheduled-without-time section."""
    if not entries:
        return 0

    row_count = _add_section_row(
        table,
        "Scheduled without specific time",
        color_enabled=render.color_enabled,
    )
    for node in entries:
        row_count += _add_task_row(
            table,
            _TaskRow(node=node, time_text=""),
            render,
        )
    return row_count


def _render_deadline_untimed_section(
    table: Table,
    entries: list[Heading],
    render: _RenderContext,
) -> int:
    """Render the deadline-without-time section."""
    if not entries:
        return 0

    row_count = _add_section_row(
        table,
        "Deadlines without specific time",
        color_enabled=render.color_enabled,
    )
    for node in entries:
        row_count += _add_task_row(
            table,
            _TaskRow(node=node, time_text=""),
            render,
        )
    return row_count


def _render_day_rows(table: Table, day_render: _DayRenderInput, render: _RenderContext) -> int:
    """Render one day's rows and return the number of added table rows."""
    row_count = 0

    row_count += _render_hour_rows(table, day_render, render)
    row_count += _render_relative_section(
        table,
        _RelativeSectionInput(
            label="Overdue deadlines",
            entries=day_render.entries.overdue_deadline,
            style="bold red" if render.color_enabled else "",
            direction="past",
        ),
        render=render,
    )
    row_count += _render_relative_section(
        table,
        _RelativeSectionInput(
            label="Overdue scheduled",
            entries=day_render.entries.overdue_scheduled,
            style="orange3" if render.color_enabled else "",
            direction="past",
        ),
        render=render,
    )
    row_count += _render_deadline_untimed_section(
        table,
        day_render.entries.deadline_untimed,
        render,
    )
    row_count += _render_scheduled_untimed_section(
        table,
        day_render.entries.scheduled_untimed,
        render,
    )
    row_count += _render_relative_section(
        table,
        _RelativeSectionInput(
            label="Upcoming deadlines (30d)",
            entries=day_render.entries.upcoming_deadline,
            style="yellow" if render.color_enabled else "",
            direction="future",
        ),
        render=render,
    )

    return row_count


def _build_agenda_table(day: date, *, color_enabled: bool) -> Table:
    """Build the agenda table layout for one day."""
    table = Table(
        expand=True,
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style="bold" if color_enabled else "",
        show_lines=False,
        row_styles=["", "on grey11"],
    )
    table.add_column("CATEGORY", min_width=8, no_wrap=True)
    table.add_column(day.strftime("%Y-%m-%d"), width=10, no_wrap=True)
    table.add_column("TASK", ratio=1)
    table.add_column("TAGS", min_width=8, justify="right", no_wrap=True)
    return table


def _render_row_model(
    table: Table,
    row: _AgendaRow,
    render: _RenderContext,
    *,
    highlighted: bool,
) -> int:
    """Render one row model into agenda table."""
    row_style = _merge_row_style(row.style, highlighted=highlighted)

    if row.kind == "task" and row.node is not None:
        return _add_task_row(
            table,
            _TaskRow(
                node=row.node,
                time_text=row.time_text,
                style=row_style,
                prefix=row.prefix,
                state_override=row.state_override,
            ),
            render,
        )

    if row.kind == "section":
        heading = Text(row.section_label, style="bold" if render.color_enabled else "")
        table.add_row(Text(""), Text(""), heading, Text(""), style=row_style)
        return 1

    if row.kind == "hour_marker":
        table.add_row(
            Text(""),
            Text(row.time_text),
            Text("---------------", style="dim"),
            Text(""),
            style=row_style,
        )
        return 1

    if row.kind == "now_marker":
        table.add_row(
            Text(""),
            Text(row.time_text),
            Text("------ NOW ------", style="bold yellow" if render.color_enabled else ""),
            Text(""),
            style=row_style,
        )
        return 1

    return 0


def _build_interactive_rows(session: _AgendaSession) -> list[_ViewportRow]:
    """Build flattened interactive rows for scrollable viewport rendering."""
    rows: list[_ViewportRow] = []
    for day_index, day_model in enumerate(session.day_models):
        rows.append(
            _ViewportRow(kind="day_header", day=day_model.day, agenda_row=None, location=None),
        )
        rows.append(
            _ViewportRow(kind="day_rule", day=day_model.day, agenda_row=None, location=None),
        )
        for row_index, agenda_row in enumerate(day_model.rows):
            location = (day_index, row_index)
            rows.append(
                _ViewportRow(
                    kind="agenda",
                    day=day_model.day,
                    agenda_row=agenda_row,
                    location=location,
                ),
            )
        if day_index != len(session.day_models) - 1:
            rows.append(
                _ViewportRow(kind="spacer", day=day_model.day, agenda_row=None, location=None),
            )
    return rows


def _selected_viewport_row_index(
    rows: list[_ViewportRow],
    selected: tuple[int, int] | None,
) -> int | None:
    """Return viewport row index for selected task location."""
    if selected is None:
        return None
    for idx, row in enumerate(rows):
        if row.location == selected:
            return idx
    return None


def _build_interactive_viewport_table() -> Table:
    """Build a table used for one interactive viewport frame."""
    table = Table(
        expand=True,
        box=None,
        show_header=False,
        show_lines=False,
        pad_edge=False,
    )
    table.add_column(min_width=8, no_wrap=True, overflow="ellipsis")
    table.add_column(width=10, no_wrap=True, overflow="ellipsis")
    table.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
    table.add_column(min_width=8, justify="right", no_wrap=True, overflow="ellipsis")
    return table


def _render_viewport_row(
    table: Table,
    row: _ViewportRow,
    session: _AgendaSession,
    selected_location: tuple[int, int] | None,
) -> None:
    """Render one viewport row preserving Rich styles and alignment."""
    if row.kind == "day_header":
        bold_style = "bold" if session.render.color_enabled else ""
        table.add_row(
            Text(""),
            Text(""),
            Text(row.day.strftime("%A %Y-%m-%d"), style=bold_style),
            Text(""),
        )
        return

    if row.kind == "day_rule":
        table.add_row(Text(""), Text(""), Text(""), Text(""))
        return

    if row.kind == "spacer":
        table.add_row(Text(""), Text(""), Text(""), Text(""))
        return

    if row.agenda_row is None:
        return

    highlighted = selected_location == row.location
    _render_row_model(table, row.agenda_row, session.render, highlighted=highlighted)


def _interactive_agenda_renderable(console: Console, session: _AgendaSession) -> Group:
    """Build scrollable interactive agenda renderable with fixed footer controls."""
    _refresh_session_if_minute_changed(session)
    rows = _build_interactive_rows(session)
    viewport_height = max(5, console.size.height - 3)
    selected_row = _selected_viewport_row_index(rows, _selected_row_location(session))

    max_offset = max(0, len(rows) - viewport_height)
    session.scroll_offset = min(max(session.scroll_offset, 0), max_offset)

    if selected_row is not None:
        if selected_row < session.scroll_offset:
            session.scroll_offset = selected_row
        elif selected_row >= session.scroll_offset + viewport_height:
            session.scroll_offset = selected_row - viewport_height + 1
        session.scroll_offset = min(max(session.scroll_offset, 0), max_offset)

    window = rows[session.scroll_offset : session.scroll_offset + viewport_height]
    table = _build_interactive_viewport_table()
    selected_location = _selected_row_location(session)
    for row in window:
        _render_viewport_row(table, row, session, selected_location)

    for _ in range(viewport_height - len(window)):
        table.add_row(Text(""), Text(""), Text(""), Text(""))

    controls = (
        "n/p, Up/Down, Wheel select"
        " | Enter edit"
        " | $ archive"
        " | f/b, Left/Right span"
        " | t state"
        " | Shift+Left/Right day"
        " | Shift+Up/Down hour"
        " | r refile"
        " | c clock"
        " | q/Esc quit"
    )
    end_line = min(session.scroll_offset + viewport_height, len(rows))
    total_lines = max(len(rows), 1)
    scroll_text = f"Lines {end_line}/{total_lines}"
    status = session.status_message or ""
    footer_style = "dim" if session.render.color_enabled else ""
    footer_line = Table.grid(expand=True)
    footer_line.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
    footer_line.add_column(ratio=4, justify="right", no_wrap=True, overflow="ellipsis")
    footer_line.add_row(
        Text(scroll_text, style=footer_style, no_wrap=True, overflow="ellipsis"),
        Text(controls, style=footer_style, no_wrap=True, overflow="ellipsis"),
    )
    return Group(
        table,
        Rule(style=footer_style),
        footer_line,
        Text(status, style=footer_style, no_wrap=True, overflow="ellipsis"),
    )


def _edit_selected_task_in_external_editor(session: _AgendaSession) -> None:
    """Edit selected task subtree in configured external editor."""
    row = _selected_task_row(session)
    if row is None or row.node is None:
        session.status_message = "Action available only on task rows"
        return

    session.status_message = ""
    try:
        edit_result = edit_heading_subtree_in_external_editor(row.node)
    except typer.BadParameter as err:
        session.status_message = str(err)
        return

    if not edit_result.changed:
        session.status_message = "No changes."
        return

    _save_document_changes(edit_result.heading.document)
    preserve_identity = _heading_identity(edit_result.heading)
    _reload_session_nodes(session)
    _refresh_session(session, preserve_identity)
    session.status_message = "Task updated"


def _archive_selected_task(session: _AgendaSession) -> None:
    """Archive selected task subtree using shared archive-location rules."""
    row = _selected_task_row(session)
    if row is None or row.node is None:
        session.status_message = "Action available only on task rows"
        return

    session.status_message = ""
    try:
        archive_result = archive_heading_subtree_and_save(row.node, {})
    except typer.BadParameter as err:
        session.status_message = str(err)
        return

    preserve_identity = _heading_identity(archive_result.heading)
    _reload_session_nodes(session)
    _refresh_session(session, preserve_identity)
    session.status_message = "Task archived"


def _shift_planning_for_row(row: _AgendaRow, *, day_delta: int) -> tuple[Timestamp | None, str]:
    """Resolve planning timestamp to shift based on selected row source."""
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


def _shift_planning_time_for_row(
    row: _AgendaRow,
    *,
    hour_delta: int,
) -> tuple[Timestamp | None, str]:
    """Shift selected timed planning timestamp by an hour delta."""
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


def _choose_state(console: Console, heading: Heading) -> str | None:
    """Prompt for a new TODO state from document states."""
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


def _apply_state_change(console: Console, session: _AgendaSession) -> None:
    """Apply interactive TODO-state transition on selected task."""
    row = _selected_task_row(session)
    if row is None or row.node is None:
        session.status_message = "Action available only on task rows"
        return

    heading = row.node
    new_state = _choose_state(console, heading)
    if new_state is None:
        session.status_message = "State change cancelled"
        return

    old_state = heading.todo
    if old_state == new_state:
        session.status_message = "State unchanged"
        return

    action_now = local_now()
    heading.todo = new_state
    append_repeat_transition(heading, old_state, new_state, action_now)

    if heading.scheduled is not None and _advance_timestamp_by_repeater(heading.scheduled):
        logger.info(
            "Agenda repeater advance: file=%s title=%s id=%s field=scheduled value=%s",
            heading.document.filename,
            heading.title_text,
            heading.id,
            heading.scheduled,
        )
    if heading.deadline is not None and _advance_timestamp_by_repeater(heading.deadline):
        logger.info(
            "Agenda repeater advance: file=%s title=%s id=%s field=deadline value=%s",
            heading.document.filename,
            heading.title_text,
            heading.id,
            heading.deadline,
        )

    logger.info(
        "Agenda set state: file=%s title=%s id=%s from=%s to=%s",
        heading.document.filename,
        heading.title_text,
        heading.id,
        old_state,
        new_state,
    )
    _save_document_changes(heading.document)
    preserve_identity = _heading_identity(heading)
    _reload_session_nodes(session)
    _refresh_session(session, preserve_identity)
    session.status_message = f"State updated: {old_state or '-'} -> {new_state}"


def _apply_shift_date(session: _AgendaSession, *, day_delta: int) -> None:
    """Shift selected task planning date by one day."""
    row = _selected_task_row(session)
    if row is None or row.node is None:
        session.status_message = "Action available only on task rows"
        return

    timestamp, status = _shift_planning_for_row(row, day_delta=day_delta)
    if timestamp is None:
        session.status_message = status
        return

    heading = row.node
    _save_document_changes(heading.document)
    preserve_identity = _heading_identity(heading)
    _reload_session_nodes(session)
    _refresh_session(session, preserve_identity)
    session.status_message = status


def _apply_shift_time(session: _AgendaSession, *, hour_delta: int) -> None:
    """Shift selected timed planning timestamp by one hour."""
    row = _selected_task_row(session)
    if row is None or row.node is None:
        session.status_message = "Action available only on task rows"
        return

    timestamp, status = _shift_planning_time_for_row(row, hour_delta=hour_delta)
    if timestamp is None:
        session.status_message = status
        return

    heading = row.node
    _save_document_changes(heading.document)
    preserve_identity = _heading_identity(heading)
    _reload_session_nodes(session)
    _refresh_session(session, preserve_identity)
    session.status_message = status


def _move_heading_to_document(heading: Heading, destination: Document) -> None:
    """Move heading subtree to destination document root."""
    parent = heading.parent
    if parent is None:
        raise ValueError("Cannot refile heading without parent")
    parent.children.remove(heading)
    destination.children.append(heading)
    heading.document = destination
    for descendant in iter_descendants(heading):
        descendant.document = destination


def _apply_refile(console: Console, session: _AgendaSession) -> None:
    """Prompt and refile selected task into another file."""
    row = _selected_task_row(session)
    if row is None or row.node is None:
        session.status_message = "Action available only on task rows"
        return

    current_files = resolve_input_paths(session.args.files)
    console.print("Refile destination:")
    for index, filename in enumerate(current_files, start=1):
        console.print(f"{index}) {filename}")
    destination_input = console.input("Destination file (# or path, blank cancels): ").strip()
    if not destination_input:
        session.status_message = "Refile cancelled"
        return

    if destination_input.isdigit():
        index = int(destination_input) - 1
        if not (0 <= index < len(current_files)):
            session.status_message = "Invalid destination shortcut"
            return
        destination_path = current_files[index]
    else:
        destination_path = destination_input

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
    logger.info(
        "Agenda refile: title=%s id=%s source=%s destination=%s",
        heading.title_text,
        heading.id,
        source_document.filename,
        destination_document.filename,
    )
    _save_document_changes(destination_document)
    if source_document is not destination_document:
        _save_document_changes(source_document)

    _reload_session_nodes(session)
    _refresh_session(session, None)
    session.status_message = f"Refiled task to {destination_doc_path}"


def _apply_clock_entry(console: Console, session: _AgendaSession) -> None:
    """Prompt and append one clock entry ending now to selected task."""
    row = _selected_task_row(session)
    if row is None or row.node is None:
        session.status_message = "Action available only on task rows"
        return

    duration_input = console.input(
        "Clock duration (H:MM, Xm, Xh, minutes; blank cancels): ",
    ).strip()
    if not duration_input:
        session.status_message = "Clock action cancelled"
        return

    try:
        duration = _parse_clock_duration(duration_input)
    except ValueError as err:
        session.status_message = str(err)
        return

    action_now = local_now()
    end_time = action_now.replace(second=0, microsecond=0)
    start_time = end_time - duration
    timestamp = Timestamp.from_source(
        f"[{start_time:%Y-%m-%d %a %H:%M}]--[{end_time:%Y-%m-%d %a %H:%M}]",
    )
    duration_text = _duration_to_org_text(duration)
    clock_entry = Clock(timestamp=timestamp, duration=duration_text)

    heading = row.node
    heading.clock_entries.append(clock_entry)
    logger.info(
        "Agenda add clock: file=%s title=%s id=%s start=%s end=%s duration=%s",
        heading.document.filename,
        heading.title_text,
        heading.id,
        start_time,
        end_time,
        duration_text,
    )

    _save_document_changes(heading.document)
    preserve_identity = _heading_identity(heading)
    _reload_session_nodes(session)
    _refresh_session(session, preserve_identity)
    session.status_message = f"Added clock entry ({duration_text})"


def _create_agenda_session(
    args: AgendaArgs,
    nodes: list[Heading],
    done_states: list[str],
    todo_states: list[str],
    color_enabled: bool,
) -> _AgendaSession:
    """Create interactive session state for agenda."""
    session = _AgendaSession(
        args=args,
        nodes=nodes,
        render=_RenderContext(
            color_enabled=color_enabled,
            done_states=done_states,
            todo_states=todo_states,
        ),
        start_date=_resolve_agenda_start_date(args.date),
        days=args.days,
        now=local_now(),
        day_models=[],
        row_locations=[],
        selected_row_index=0,
        scroll_offset=0,
        status_message="",
    )
    _refresh_session(session, None)
    return session


def _agenda_key_bindings(
    console: Console,
    session: _AgendaSession,
) -> dict[str, KeyBinding]:
    """Build interactive key bindings for agenda session."""
    return {
        "q": KeyBinding(lambda: False),
        "ESC": KeyBinding(lambda: False),
        "n": key_binding_for_action(lambda: _move_selection(session, 1)),
        "DOWN": key_binding_for_action(lambda: _move_selection(session, 1)),
        "WHEEL-DOWN": key_binding_for_action(lambda: _move_selection(session, 1)),
        "p": key_binding_for_action(lambda: _move_selection(session, -1)),
        "UP": key_binding_for_action(lambda: _move_selection(session, -1)),
        "WHEEL-UP": key_binding_for_action(lambda: _move_selection(session, -1)),
        "f": key_binding_for_action(
            lambda: _set_start_date_relative(session, day_delta=session.days),
        ),
        "RIGHT": key_binding_for_action(
            lambda: _set_start_date_relative(session, day_delta=session.days),
        ),
        "b": key_binding_for_action(
            lambda: _set_start_date_relative(session, day_delta=-session.days),
        ),
        "LEFT": key_binding_for_action(
            lambda: _set_start_date_relative(session, day_delta=-session.days),
        ),
        "ENTER": key_binding_for_action(
            lambda: _edit_selected_task_in_external_editor(session),
            requires_live_pause=True,
        ),
        "$": key_binding_for_action(lambda: _archive_selected_task(session)),
        "t": key_binding_for_action(
            lambda: _apply_state_change(console, session),
            requires_live_pause=True,
        ),
        "S-LEFT": key_binding_for_action(lambda: _apply_shift_date(session, day_delta=-1)),
        "S-RIGHT": key_binding_for_action(lambda: _apply_shift_date(session, day_delta=1)),
        "S-UP": key_binding_for_action(lambda: _apply_shift_time(session, hour_delta=-1)),
        "S-DOWN": key_binding_for_action(lambda: _apply_shift_time(session, hour_delta=1)),
        "r": key_binding_for_action(
            lambda: _apply_refile(console, session),
            requires_live_pause=True,
        ),
        "c": key_binding_for_action(
            lambda: _apply_clock_entry(console, session),
            requires_live_pause=True,
        ),
    }


def _set_start_date_relative(session: _AgendaSession, *, day_delta: int) -> None:
    """Shift agenda start date by one relative day delta and refresh."""
    session.start_date += timedelta(days=day_delta)
    _refresh_session(session, None)


def _handle_interactive_key(console: Console, session: _AgendaSession, key: str) -> bool:
    """Handle one interactive keypress and return whether to continue."""
    _refresh_session_if_minute_changed(session)

    result = dispatch_key_binding(key, _agenda_key_bindings(console, session))
    if result.handled:
        return result.continue_loop

    if key:
        session.status_message = f"Unsupported key: {key}"
    return True


def _run_agenda_interactive(console: Console, session: _AgendaSession) -> None:
    """Run interactive agenda event loop."""
    set_mouse_reporting(True)
    try:
        with Live(
            _interactive_agenda_renderable(console, session),
            console=console,
            screen=True,
            refresh_per_second=12,
            auto_refresh=False,
        ) as live:
            while True:
                key = read_keypress(timeout_seconds=0.2)
                if not key:
                    live.update(_interactive_agenda_renderable(console, session), refresh=True)
                    continue
                if key_binding_requires_live_pause(key, _agenda_key_bindings(console, session)):
                    live.stop()
                    should_continue = _handle_interactive_key(console, session, key)
                    live.start()
                else:
                    should_continue = _handle_interactive_key(console, session, key)
                if not should_continue:
                    break
                live.update(_interactive_agenda_renderable(console, session), refresh=True)
    finally:
        set_mouse_reporting(False)


def _render_agenda(console: Console, render_input: _AgendaRenderInput) -> None:
    """Render agenda output table."""
    start_date = _resolve_agenda_start_date(render_input.args.date)
    rendered_tables: list[Table] = []
    total_rows = 0
    for day_offset in range(render_input.args.days):
        day = start_date + timedelta(days=day_offset)
        table = _build_agenda_table(day, color_enabled=render_input.render.color_enabled)
        entries = _collect_day_entries(
            render_input.nodes,
            day,
            render_input.args,
            include_relative_sections=(day == render_input.now.date()),
        )
        day_rows = _render_day_rows(
            table,
            _DayRenderInput(day=day, now=render_input.now, entries=entries),
            render_input.render,
        )
        total_rows += day_rows + 2
        rendered_tables.append(table)

    if total_rows > console.height:
        with console.pager(styles=render_input.render.color_enabled):
            for idx, table in enumerate(rendered_tables):
                console.print(table)
                if idx != len(rendered_tables) - 1:
                    console.print()
        return

    for idx, table in enumerate(rendered_tables):
        console.print(table)
        if idx != len(rendered_tables) - 1:
            console.print()


def run_agenda(args: AgendaArgs) -> None:
    """Run the agenda command."""
    color_enabled = setup_output(args)
    console = build_console(color_enabled, args.width)

    if args.offset < 0:
        raise typer.BadParameter("--offset must be non-negative")
    if args.max_results is not None and args.max_results < 0:
        raise typer.BadParameter("--limit must be non-negative")
    if args.days < 1:
        raise typer.BadParameter("--days must be at least 1")

    args.max_results = _resolve_tasks_limit(args.max_results)

    with processing_status(console, color_enabled):
        nodes, todo_states, done_states = load_and_process_data(args)

    if not nodes:
        console.print("No results", markup=False)
        return

    if sys.stdin.isatty() and sys.stdout.isatty():
        _run_agenda_interactive(
            console,
            _create_agenda_session(
                args,
                nodes,
                done_states,
                todo_states,
                color_enabled,
            ),
        )
        return

    _render_agenda(
        console,
        _AgendaRenderInput(
            args=args,
            nodes=nodes,
            now=local_now(),
            render=_RenderContext(
                color_enabled=color_enabled,
                done_states=done_states,
                todo_states=todo_states,
            ),
        ),
    )


def register(app: typer.Typer) -> None:
    """Register the agenda command."""

    @app.command(
        "agenda",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )
    def agenda(  # noqa: PLR0913
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
        date: str | None = typer.Option(
            None,
            "--date",
            metavar="DATE",
            help="Agenda start date (default: today). Formats: YYYY-MM-DD or ISO datetime",
        ),
        days: int = typer.Option(
            1,
            "--days",
            metavar="N",
            min=1,
            help="How many days to show starting from --date",
        ),
        no_completed: bool = typer.Option(
            False,
            "--no-completed",
            help="Omit tasks in completed states (including repeats)",
        ),
        no_overdue: bool = typer.Option(
            False,
            "--no-overdue",
            help="Omit overdue scheduled and deadline tasks",
        ),
        no_upcoming: bool = typer.Option(
            False,
            "--no-upcoming",
            help="Omit upcoming deadlines",
        ),
    ) -> None:
        """Show agenda for one day or a date range."""
        args = AgendaArgs(
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
            offset=offset,
            order_by_level=order_by_level,
            order_by_file_order=order_by_file_order,
            order_by_file_order_reversed=order_by_file_order_reversed,
            order_by_priority=order_by_priority,
            order_by_timestamp_asc=order_by_timestamp_asc,
            order_by_timestamp_desc=order_by_timestamp_desc,
            with_tags_as_category=with_tags_as_category,
            date=date,
            days=days,
            no_completed=no_completed,
            no_overdue=no_overdue,
            no_upcoming=no_upcoming,
        )
        config_module.apply_config_defaults(args)
        config_module.log_applied_config_defaults(args, sys.argv[1:], "agenda")
        config_module.log_command_arguments(args, "agenda")
        run_agenda(args)
