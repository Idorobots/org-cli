"""Agenda command for day-based task planning views."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import typer
from rich import box
from rich.table import Table
from rich.text import Text

from org import config as config_module
from org.cli_common import load_and_process_data
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
    from org_parser.document import Heading
    from org_parser.element import Repeat
    from org_parser.time import Timestamp
    from rich.console import Console


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


def _has_specific_time(timestamp: Timestamp) -> bool:
    """Return whether an org timestamp includes an explicit start time."""
    return timestamp.start_hour is not None


def _is_active_planning_timestamp(timestamp: Timestamp | None) -> bool:
    """Return whether a planning timestamp is present and active."""
    return bool(timestamp is not None and timestamp.is_active)


def _resolve_agenda_start_date(raw_date: str | None) -> date:
    """Resolve agenda start date from --date or today's date."""
    if raw_date is None:
        return _local_now().date()
    return parse_date_argument(raw_date, "--date").date()


def _local_now() -> datetime:
    """Return local timezone-aware current datetime."""
    return datetime.now(tz=UTC).astimezone()


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
    color_enabled: bool,
    done_states: list[str],
    todo_states: list[str],
    prefix: str | None = None,
) -> Text:
    """Build heading cell text with state, priority, and rich title."""
    heading = Text()
    if prefix:
        heading.append(prefix, style="dim" if color_enabled else "")

    state = node.todo or ""
    if state:
        heading.append_text(
            task_state_prefix_to_text(
                state,
                done_states=done_states,
                todo_states=todo_states,
                color_enabled=color_enabled,
            ),
        )

    heading.append_text(task_priority_to_text(node.priority, color_enabled, trailing_space=True))

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
    done_states: list[str],
    *,
    no_completed: bool,
) -> list[_TimedEntry]:
    """Collect completed repeat entries for one day."""
    timed: list[_TimedEntry] = []
    if no_completed:
        return timed

    repeats: list[Repeat] = [repeat for repeat in node.repeats if repeat.after in done_states]
    for repeat in repeats:
        repeat_day = repeat.timestamp.start.date()
        if repeat_day != day:
            continue
        if _has_specific_time(repeat.timestamp):
            timed.append(_TimedEntry(node=node, when=repeat.timestamp.start, kind="repeat"))
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
    done_states: list[str],
    args: AgendaArgs,
    *,
    include_relative_sections: bool,
) -> _DayEntries:
    """Collect and group agenda entries for one day."""
    timed: list[_TimedEntry] = []
    overdue_scheduled: list[_RelativeEntry] = []
    overdue_deadline: list[_RelativeEntry] = []
    scheduled_untimed: list[Heading] = []
    upcoming_deadline: list[_RelativeEntry] = []

    upcoming_limit = day + timedelta(days=30)

    for node in nodes:
        completed = node.is_completed
        if args.no_completed and completed:
            continue

        scheduled_timed, scheduled_day_untimed = _collect_scheduled_entries(node, day)
        timed.extend(scheduled_timed)
        if not completed:
            scheduled_untimed.extend(scheduled_day_untimed)

        repeat_timed = _collect_repeat_timed_entries(
            node,
            day,
            done_states,
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
    return _DayEntries(
        timed=timed,
        overdue_scheduled=overdue_scheduled,
        overdue_deadline=overdue_deadline,
        scheduled_untimed=scheduled_untimed,
        upcoming_deadline=upcoming_deadline,
    )


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
            color_enabled=render.color_enabled,
            done_states=render.done_states,
            todo_states=render.todo_states,
            prefix=row.prefix,
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
            prefix="DEADLINE ",
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
            prefix="DEADLINE ",
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
            render_input.render.done_states,
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

    _render_agenda(
        console,
        _AgendaRenderInput(
            args=args,
            nodes=nodes,
            now=_local_now(),
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
            ".org-cli.json",
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
