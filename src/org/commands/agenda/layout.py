"""Agenda interactive and static layout helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

import org_parser.time as org_time
from rich import box
from rich.console import Console, Group
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from org.commands.interactive_common import (
    INTERACTIVE_HELP_FOOTER_HINT,
    InteractiveHelpEntry,
    build_footer_prompt_text,
    local_now,
    render_interactive_help_modal,
    shift_datetimes_by_unit,
)
from org.tui import (
    heading_title_to_text,
    task_priority_to_text,
    task_state_prefix_to_text,
    task_tags_to_text,
)
from org.validation import parse_date_argument


if TYPE_CHECKING:
    from collections.abc import Sequence

    from org_parser.document import Heading

    from .command import AgendaArgs

AgendaRowLike = Any
AgendaSessionLike = Any


_HIGHLIGHT_ROW_STYLE = "on grey23"
Timestamp = org_time.Timestamp


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


_AGENDA_HELP_ENTRIES = [
    InteractiveHelpEntry("Esc/q", "Exit the agenda view and return to the shell."),
    InteractiveHelpEntry(
        "n/p, Up/Down, Wheel",
        "Move selection across visible agenda rows, including non-task rows.",
    ),
    InteractiveHelpEntry(
        "f/b, Left/Right",
        "Move the agenda window forward or backward by the current --days span.",
    ),
    InteractiveHelpEntry(
        "Enter",
        "Open the selected task subtree in the external editor workflow.",
    ),
    InteractiveHelpEntry(
        "a",
        "Capture a task from templates, prefilled for the selected timed row when available.",
    ),
    InteractiveHelpEntry(
        "$",
        "Archive the selected task subtree using standard archive rules.",
    ),
    InteractiveHelpEntry(
        "/",
        "Open search prompt and filter visible tasks by task text.",
    ),
    InteractiveHelpEntry(
        "x",
        "Clear active search filter and restore full agenda.",
    ),
    InteractiveHelpEntry(
        "t",
        "Prompt for a TODO state and apply it to the selected task with repeat transition logging.",
    ),
    InteractiveHelpEntry(
        "S-Left/S-Right",
        "Shift selected task planning date backward or forward by one day.",
    ),
    InteractiveHelpEntry(
        "S-Up/S-Down",
        "Shift selected timed scheduled/deadline rows by one hour.",
    ),
    InteractiveHelpEntry(
        "r",
        "Refile the selected task to another loaded file destination.",
    ),
    InteractiveHelpEntry(
        "c",
        "Add a clock entry ending now using a prompted duration.",
    ),
]


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


def _planning_matches_day(timestamp: Timestamp, day: date, *, future_repeats: bool) -> bool:
    """Return whether a planning timestamp should appear on the target day."""
    if not _is_active_planning_timestamp(timestamp):
        return False

    start = timestamp.start
    start_day = start.date()
    if start_day == day:
        return True

    repeat_value, repeat_unit = _repeater_for_future_match(timestamp)
    should_expand = _should_expand_future_repeats(
        future_repeats=future_repeats,
        repeat_value=repeat_value,
        day=day,
        start_day=start_day,
    )
    if not should_expand:
        return False

    matches = False
    if repeat_unit == "h":
        matches = _hourly_repeater_matches_day(start, day, repeat_value)
    elif repeat_unit in {"d", "w"}:
        matches = _daily_or_weekly_repeater_matches_day(start_day, day, repeat_value, repeat_unit)
    elif repeat_unit in {"m", "y"}:
        matches = _monthly_or_yearly_repeater_matches_day(start, day, repeat_value, repeat_unit)
    return matches


def _repeater_for_future_match(timestamp: Timestamp) -> tuple[int, str | None]:
    """Extract repeat value and unit for potential future repeat matching."""
    if timestamp.repeater is None:
        return 0, None
    return timestamp.repeater.value, timestamp.repeater.unit


def _should_expand_future_repeats(
    *,
    future_repeats: bool,
    repeat_value: int,
    day: date,
    start_day: date,
) -> bool:
    """Check whether potential future repeat expansion should be attempted."""
    return future_repeats and repeat_value > 0 and day >= start_day


def _hourly_repeater_matches_day(start: datetime, day: date, repeat_value: int) -> bool:
    """Return whether an hourly repeater has an occurrence on the target day."""
    day_start = datetime.combine(day, datetime.min.time())
    day_end = day_start + timedelta(days=1) - timedelta(microseconds=1)
    step = timedelta(hours=repeat_value)
    min_delta = day_start - start
    max_delta = day_end - start
    min_step = int(min_delta // step)
    max_step = int(max_delta // step)
    first_step = max(min_step, 0)
    return first_step <= max_step and (start + step * first_step).date() == day


def _daily_or_weekly_repeater_matches_day(
    start_day: date,
    day: date,
    repeat_value: int,
    repeat_unit: str,
) -> bool:
    """Return whether a daily or weekly repeater lands on the target day."""
    repeat_days = repeat_value if repeat_unit == "d" else repeat_value * 7
    return (day - start_day).days % repeat_days == 0


def _monthly_or_yearly_repeater_matches_day(
    start: datetime,
    day: date,
    repeat_value: int,
    repeat_unit: str,
) -> bool:
    """Return whether a monthly/yearly repeater lands on the target day."""
    next_start = start
    for _ in range(20000):
        shifted_start, _ = shift_datetimes_by_unit(
            next_start,
            None,
            value=repeat_value,
            unit=repeat_unit,
        )
        shifted_day = shifted_start.date()
        if shifted_day == day:
            return True
        if shifted_day > day:
            return False
        next_start = shifted_start
    return False


def _collect_repeat_timed_entries(
    node: Heading,
    day: date,
    *,
    no_completed: bool,
) -> list[_TimedEntry]:
    """Collect completed repeat entries for one day."""
    if no_completed:
        return []

    timed: list[_TimedEntry] = []
    repeats = [repeat for repeat in node.repeats if repeat.is_completed]
    for repeat in repeats:
        if repeat.timestamp.start.date() != day:
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


def _collect_scheduled_entries(
    node: Heading,
    day: date,
    *,
    future_repeats: bool,
) -> tuple[list[_TimedEntry], list[Heading]]:
    """Collect scheduled entries on one day."""
    timed: list[_TimedEntry] = []
    untimed: list[Heading] = []
    if node.scheduled is None or not _planning_matches_day(
        node.scheduled,
        day,
        future_repeats=future_repeats,
    ):
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
    future_repeats: bool,
) -> tuple[list[_TimedEntry], list[Heading]]:
    """Collect deadline entries on one day for incomplete tasks."""
    timed: list[_TimedEntry] = []
    untimed: list[Heading] = []
    if completed or not _is_active_planning_timestamp(node.deadline) or node.deadline is None:
        return timed, untimed
    if not _planning_matches_day(node.deadline, day, future_repeats=future_repeats):
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

        scheduled_timed, scheduled_day_untimed = _collect_scheduled_entries(
            node,
            day,
            future_repeats=args.future_repeats,
        )
        timed.extend(scheduled_timed)
        if not completed:
            scheduled_untimed.extend(scheduled_day_untimed)

        deadline_timed, deadline_day_untimed = _collect_deadline_entries(
            node,
            day,
            completed=completed,
            future_repeats=args.future_repeats,
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

        timed.extend(
            _collect_repeat_timed_entries(node, day, no_completed=args.no_completed),
        )

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
        rows.append(_AgendaRow(kind="hour_marker", day=day_render.day, time_text=f"{hour:02d}:00"))
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


def _relative_section_rows(day: date, spec: _RelativeRowsSpec) -> list[_AgendaRow]:
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
        _AgendaRow(kind="task", day=day, node=node, source="scheduled_untimed") for node in entries
    )
    return rows


def _deadline_untimed_rows(day: date, entries: list[Heading]) -> list[_AgendaRow]:
    """Build rows for deadline-without-time section."""
    if not entries:
        return []
    rows = [_AgendaRow(kind="section", day=day, section_label="Deadlines without specific time")]
    rows.extend(
        _AgendaRow(kind="task", day=day, node=node, source="deadline_today") for node in entries
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


def _selected_row_location(session: AgendaSessionLike) -> tuple[int, int] | None:
    """Return selected day/row indexes or None when no rows exist."""
    if not session.row_locations:
        return None
    return cast("tuple[int, int]", session.row_locations[session.selected_row_index])


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
    if not section.entries:
        return 0
    row_count = _add_section_row(
        table,
        section.label,
        color_enabled=render.color_enabled,
        style=section.style,
    )
    for entry in section.entries:
        row_count += _add_task_row(
            table,
            _TaskRow(
                node=entry.node,
                time_text=_format_relative_days(
                    entry.delta_days,
                    in_future=section.direction == "future",
                ),
                style=section.style,
                prefix=section.prefix,
            ),
            render,
        )
    return row_count


def _render_scheduled_untimed_section(
    table: Table,
    entries: Sequence[Heading],
    render: _RenderContext,
) -> int:
    if not entries:
        return 0
    row_count = _add_section_row(
        table,
        "Scheduled without specific time",
        color_enabled=render.color_enabled,
    )
    for node in entries:
        row_count += _add_task_row(table, _TaskRow(node=node, time_text=""), render)
    return row_count


def _render_deadline_untimed_section(
    table: Table,
    entries: Sequence[Heading],
    render: _RenderContext,
) -> int:
    if not entries:
        return 0
    row_count = _add_section_row(
        table,
        "Deadlines without specific time",
        color_enabled=render.color_enabled,
    )
    for node in entries:
        row_count += _add_task_row(table, _TaskRow(node=node, time_text=""), render)
    return row_count


def _render_day_rows(table: Table, day_render: _DayRenderInput, render: _RenderContext) -> int:
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
        render,
    )
    row_count += _render_relative_section(
        table,
        _RelativeSectionInput(
            label="Overdue scheduled",
            entries=day_render.entries.overdue_scheduled,
            style="orange3" if render.color_enabled else "",
            direction="past",
        ),
        render,
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
        render,
    )
    return row_count


def _build_agenda_table(day: date, *, color_enabled: bool) -> Table:
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
    row: AgendaRowLike,
    render: _RenderContext,
    *,
    highlighted: bool,
) -> int:
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


def _build_interactive_rows(session: AgendaSessionLike) -> list[_ViewportRow]:
    rows: list[_ViewportRow] = []
    for day_index, day_model in enumerate(session.day_models):
        rows.append(
            _ViewportRow(kind="day_header", day=day_model.day, agenda_row=None, location=None),
        )
        rows.append(
            _ViewportRow(kind="day_rule", day=day_model.day, agenda_row=None, location=None),
        )
        for row_index, agenda_row in enumerate(day_model.rows):
            rows.append(
                _ViewportRow(
                    kind="agenda",
                    day=day_model.day,
                    agenda_row=_AgendaRow(
                        kind=agenda_row.kind,
                        day=agenda_row.day,
                        time_text=agenda_row.time_text,
                        section_label=agenda_row.section_label,
                        node=agenda_row.node,
                        source=agenda_row.source,
                        style=agenda_row.style,
                        prefix=agenda_row.prefix,
                        state_override=agenda_row.state_override,
                    ),
                    location=(day_index, row_index),
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
    if selected is None:
        return None
    for idx, row in enumerate(rows):
        if row.location == selected:
            return idx
    return None


def _build_interactive_viewport_table() -> Table:
    table = Table(expand=True, box=None, show_header=False, show_lines=False, pad_edge=False)
    table.add_column(min_width=8, no_wrap=True, overflow="ellipsis")
    table.add_column(width=10, no_wrap=True, overflow="ellipsis")
    table.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
    table.add_column(min_width=8, justify="right", no_wrap=True, overflow="ellipsis")
    return table


def _render_viewport_row(
    table: Table,
    row: _ViewportRow,
    session: AgendaSessionLike,
    selected_location: tuple[int, int] | None,
) -> None:
    if row.kind in {"day_rule", "spacer"}:
        table.add_row(Text(""), Text(""), Text(""), Text(""))
        return
    if row.kind == "day_header":
        bold_style = "bold" if session.render.color_enabled else ""
        table.add_row(
            Text(""),
            Text(""),
            Text(row.day.strftime("%A %Y-%m-%d"), style=bold_style),
            Text(""),
        )
        return
    if row.agenda_row is None:
        return
    _render_row_model(
        table,
        row.agenda_row,
        session.render,
        highlighted=selected_location == row.location,
    )


def interactive_agenda_renderable(console: Console, session: AgendaSessionLike) -> Group:
    """Build scrollable interactive agenda renderable with fixed footer controls."""
    if session.show_help_modal:
        return Group(
            render_interactive_help_modal(
                _AGENDA_HELP_ENTRIES,
                color_enabled=session.render.color_enabled,
            ),
        )
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
    selected_location = _selected_row_location(session)
    viewport_table = _build_interactive_viewport_table()
    for row in window:
        _render_viewport_row(viewport_table, row, session, selected_location)
    for _ in range(viewport_height - len(window)):
        viewport_table.add_row(Text(""), Text(""), Text(""), Text(""))
    end_line = min(session.scroll_offset + viewport_height, len(rows))
    total_lines = max(len(rows), 1)
    search_text = session.search_text or "-"
    scroll_text = f"Lines {end_line}/{total_lines} | Search: {search_text}"
    prompt_line = None
    if session.active_prompt is not None:
        prompt_line = build_footer_prompt_text(session.active_prompt.prompt)
    status = session.status_message or ""
    footer_style = "dim" if session.render.color_enabled else ""
    footer_line = Table.grid(expand=True)
    footer_line.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
    footer_line.add_column(ratio=4, justify="right", no_wrap=True, overflow="ellipsis")
    footer_line.add_row(
        Text(scroll_text, style=footer_style, no_wrap=True, overflow="ellipsis"),
        Text(INTERACTIVE_HELP_FOOTER_HINT, style=footer_style, no_wrap=True, overflow="ellipsis"),
    )
    status_text = Text(status, style=footer_style, no_wrap=True, overflow="ellipsis")
    if prompt_line is None:
        return Group(viewport_table, Rule(style=footer_style), footer_line, status_text)
    return Group(viewport_table, Rule(style=footer_style), footer_line, prompt_line, status_text)


def render_agenda(console: Console, render_input: _AgendaRenderInput) -> None:
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


AgendaRenderInput = _AgendaRenderInput
RenderContext = _RenderContext
AgendaHelpEntries = _AGENDA_HELP_ENTRIES
AgendaRow = _AgendaRow


__all__ = [
    "_AGENDA_HELP_ENTRIES",
    "_AgendaRenderInput",
    "_AgendaRow",
    "_DayEntries",
    "_DayRenderInput",
    "_DayRowModel",
    "_RelativeEntry",
    "_RelativeRowsSpec",
    "_RelativeSectionInput",
    "_RenderContext",
    "_TaskRow",
    "_TimedEntry",
    "_ViewportRow",
    "_add_section_row",
    "_add_task_row",
    "_build_day_rows",
    "_collect_day_entries",
    "_format_relative_days",
    "_has_specific_time",
    "_is_active_planning_timestamp",
    "_merge_row_style",
    "_resolve_agenda_start_date",
    "_selected_row_location",
    "interactive_agenda_renderable",
    "render_agenda",
]
