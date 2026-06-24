"""Tests for agenda command behavior and rendering."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from io import StringIO
from typing import TYPE_CHECKING, cast

import org_parser
import pytest
import typer
from org_parser.time import Timestamp
from rich.console import Console

import org.config.app
import org.logic.time
from org.commands.agenda import actions, ui
from org.commands.agenda import command as agenda_command
from org.commands.agenda.views import (
    AgendaViewContext,
    _compile_view_section_specs,
    _fallback_agenda_view,
    resolve_view_context,
)
from org.commands.tasks.common import duration_to_org_text, parse_clock_duration
from org.db.load import load_and_process_data
from org.logic.tasks import detail_org_block, heading_locator
from org.logic.time import advance_timestamp_by_repeater, local_now
from org.tui.bits import setup_output


if TYPE_CHECKING:
    from org_parser.document import Document, Heading


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def _app_config(
    *,
    agenda_views: dict[str, org.config.app.AgendaViewConfig] | None = None,
) -> org.config.app.AppConfig:
    """Build app config for agenda tests with optional configured views."""
    config = org.config.app.AppConfig(config_path=".org-cli.yaml")
    if agenda_views is not None:
        config.agenda.views = agenda_views
    return config


def _make_args(files: list[str], **overrides: object) -> agenda_command.AgendaArgs:
    args = agenda_command.AgendaArgs(
        files=files,
        config=".org-cli.yaml",
        exclude=None,
        mapping=None,
        mapping_inline=None,
        exclude_inline=None,
        todo_states="TODO",
        done_states="DONE",
        filter_priority=None,
        filter_level=None,
        filter_repeats_above=None,
        filter_repeats_below=None,
        filter_date_from=None,
        filter_date_until=None,
        filter_properties=None,
        filter_tags=None,
        filter_headings=None,
        filter_bodies=None,
        filter_completed=False,
        filter_not_completed=False,
        color_flag=False,
        width=140,
        max_results=None,
        offset=0,
        order_by_level=False,
        order_by_file_order=False,
        order_by_file_order_reversed=False,
        order_by_priority=False,
        order_by_timestamp_asc=False,
        order_by_timestamp_desc=False,
        with_tags_as_category=False,
        date=None,
        days=1,
        no_completed=False,
        no_overdue=False,
        no_upcoming=False,
        future_repeats=True,
        view=None,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def _visible_agenda_task_titles(session: object) -> list[str]:
    """Return visible task titles from current interactive agenda rows."""
    titles: list[str] = []
    typed_session = cast("actions.AgendaSession", session)
    for day_model in typed_session.day_models:
        titles.extend(
            row.node.title_text.strip()
            for row in day_model.rows
            if row.kind == "task" and row.node is not None
        )
    return titles


def _make_session(
    args: agenda_command.AgendaArgs,
    nodes: list[Heading],
    *,
    done_states: list[str] | None = None,
    todo_states: list[str] | None = None,
    color_enabled: bool = False,
) -> actions.AgendaSession:
    view = _fallback_agenda_view()
    view_ctx = AgendaViewContext(section_specs=_compile_view_section_specs(view), name=view.name)
    render = ui.RenderContext(
        color_enabled=color_enabled,
        done_states=["DONE"] if done_states is None else done_states,
        todo_states=["TODO"] if todo_states is None else todo_states,
    )
    return actions.create_agenda_session(
        args,
        _app_config(),
        nodes,
        render,
        view_ctx,
    )


def _pin_agenda_now(monkeypatch: pytest.MonkeyPatch) -> datetime:
    """Pin agenda command current time for deterministic date-sensitive tests."""
    pinned_now = datetime(2025, 1, 15, 12, 0)
    monkeypatch.setattr(actions, "local_now", lambda: pinned_now)
    monkeypatch.setattr(ui, "local_now", lambda: pinned_now)
    monkeypatch.setattr("org.logic.time.local_now", lambda: pinned_now)
    return pinned_now


def _render_agenda_output(args: agenda_command.AgendaArgs) -> str:
    """Render agenda output through shared UI helpers for rendering tests."""
    return _render_agenda_output_with_config(args, _app_config())


def _render_agenda_output_with_config(
    args: agenda_command.AgendaArgs,
    config: org.config.app.AppConfig,
) -> str:
    """Render agenda output through shared UI helpers for rendering tests."""
    color_enabled = setup_output(args)
    args.max_results = agenda_command._resolve_tasks_limit(args.max_results)
    ui.resolve_agenda_start_date(args.date)
    console_output = StringIO()
    console = Console(
        file=console_output,
        width=args.width or 140,
        height=1000,
        no_color=not color_enabled,
        force_terminal=color_enabled,
    )
    nodes, todo_states, done_states = load_and_process_data(args, config)
    ui.render_agenda(
        console,
        ui.AgendaRenderInput(
            args=args,
            nodes=nodes,
            now=org.logic.time.local_now(),
            render=ui.RenderContext(
                color_enabled=color_enabled,
                done_states=done_states,
                todo_states=todo_states,
            ),
        ),
        resolve_view_context(args, config.agenda.views),
    )
    return console_output.getvalue()


def test_run_agenda_renders_expected_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agenda should render the current view-based agenda for the selected day."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], date="2025-01-15")
    args.max_results = sys.maxsize

    monkeypatch.setattr(
        sys,
        "argv",
        ["org", "agenda", "--date", "2025-01-15", fixture_path],
    )
    output = _render_agenda_output(args)
    plain_output = output.replace("…", "")

    assert "2025-01-15" in plain_output
    assert "Timed agenda task" in plain_output
    assert "Repeated completion on day" in plain_output
    assert "Overdue deadlines" not in plain_output
    assert "Upcoming deadlines (30d)" not in plain_output
    assert "Overdue scheduled task" in plain_output
    assert "Overdue deadline task" in plain_output
    assert "Upcoming deadline task" in plain_output
    assert "Untimed agenda task" in plain_output
    assert "CATEGORY" in plain_output
    assert "TASK" in plain_output


def test_run_agenda_no_completed_hides_completed_and_repeats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agenda should hide completed states and repeat completions with --no-completed."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], date="2025-01-15", no_completed=True)

    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", "2025-01-15", "--no-completed"])
    output = _render_agenda_output(args)

    assert "Repeated completion on day" not in output
    assert "Completed one-off task" not in output


def test_run_agenda_no_overdue_hides_overdue_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agenda should hide overdue sections and rows with --no-overdue."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], date="2025-01-15", no_overdue=True)

    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", "2025-01-15", "--no-overdue"])
    output = _render_agenda_output(args)

    assert "Overdue scheduled task" not in output
    assert "Overdue deadline task" not in output


def test_run_agenda_no_upcoming_hides_upcoming_section(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agenda should hide upcoming deadline section with --no-upcoming."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], date="2025-01-15", no_upcoming=True)

    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", "2025-01-15", "--no-upcoming"])
    output = _render_agenda_output(args)

    assert "Upcoming deadlines (30d)" not in output
    assert "Upcoming deadline task" not in output


def test_run_agenda_shows_future_repeated_scheduled_by_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Future agenda day should include repeated scheduled tasks by default."""
    fixture_path = os.path.join(tmp_path, "agenda_future_repeat_scheduled.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write("* TODO Repeat scheduled\nSCHEDULED: <2025-01-15 Wed 09:30 +2d>\n")

    args = _make_args([fixture_path], date="2025-01-17")
    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", "2025-01-17", fixture_path])
    output = _render_agenda_output(args)

    assert "Repeat scheduled" in output
    assert "09:30" in output


def test_run_agenda_shows_future_repeated_deadline_by_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Future agenda day should include repeated deadline tasks by default."""
    fixture_path = os.path.join(tmp_path, "agenda_future_repeat_deadline.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write("* TODO Repeat deadline\nDEADLINE: <2025-01-15 Wed 13:15 +2d>\n")

    args = _make_args([fixture_path], date="2025-01-17")
    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", "2025-01-17", fixture_path])
    output = _render_agenda_output(args)

    assert "Repeat deadline" in output
    assert "13:15" in output


def test_run_agenda_no_future_repeats_hides_projected_repeats(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Projected repeated planning entries should be hidden with --no-future-repeats."""
    fixture_path = os.path.join(tmp_path, "agenda_no_future_repeats.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write("* TODO Repeat scheduled\nSCHEDULED: <2025-01-15 Wed 09:30 +1d>\n")

    args = _make_args([fixture_path], date="2025-01-16", future_repeats=False)
    monkeypatch.setattr(
        sys,
        "argv",
        ["org", "agenda", "--date", "2025-01-16", "--no-future-repeats", fixture_path],
    )
    output = _render_agenda_output(args)

    assert "Repeat scheduled" not in output


def test_run_agenda_days_renders_multiple_day_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agenda should render one weekday/date header per day in the requested range."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], date="2025-01-15", days=2)

    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", "2025-01-15", "--days", "2"])
    output = _render_agenda_output(args)
    plain_output = output.replace("…", "")

    assert "Wednesday 2025-01-15" in plain_output
    assert "Thursday 2025-01-16" in plain_output


def test_run_agenda_single_day_default_shows_day_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """Single-day agenda should render a weekday/date header row."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path])

    monkeypatch.setattr(sys, "argv", ["org", "agenda"])
    output = _render_agenda_output(args)
    plain_output = output.replace("…", "")
    expected_day_header = local_now().strftime("%A %Y-%m-%d")

    assert "CATEGORY" in plain_output
    assert expected_day_header in plain_output


def test_run_agenda_hides_repeat_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agenda should render repeated tasks without the REPEAT prefix."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], date="2025-01-15")

    monkeypatch.setattr(
        sys,
        "argv",
        ["org", "agenda", "--date", "2025-01-15", fixture_path],
    )
    output = _render_agenda_output(args)

    assert "REPEAT " not in output


def test_run_agenda_repeat_row_uses_repeat_after_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Repeat rows should display repeat.after state, not current heading state."""
    fixture_path = os.path.join(tmp_path, "agenda_repeat_state.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(
            "* TODO Reopened repeat task\n"
            "SCHEDULED: <2025-01-01 Wed 11:00 +10d>\n"
            ":LOGBOOK:\n"
            '- State "DONE"       from "TODO"       [2025-01-15 Wed 11:15]\n'
            '- State "TODO"       from "DONE"       [2025-01-16 Thu 11:15]\n'
            ":END:\n",
        )

    args = _make_args([fixture_path], date="2025-01-15")
    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", "2025-01-15"])
    output = _render_agenda_output(args)

    assert "DONE Reopened repeat task" in output
    assert "TODO Reopened repeat task" not in output


def test_run_agenda_excludes_completed_untimed_scheduled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Timed scheduled section should omit completed tasks when --no-completed is set."""
    fixture_path = os.path.join(tmp_path, "agenda_completed_filter.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(
            "* DONE Completed timed task\n"
            "SCHEDULED: <2025-01-15 Wed 09:00>\n\n"
            "* TODO Active timed task\n"
            "SCHEDULED: <2025-01-15 Wed 10:00>\n",
        )

    args = _make_args([fixture_path], date="2025-01-15", no_completed=True)
    monkeypatch.setattr(
        sys,
        "argv",
        ["org", "agenda", "--date", "2025-01-15", "--no-completed", fixture_path],
    )
    output = _render_agenda_output(args)

    assert "Active timed task" in output
    assert "Completed timed task" not in output


def test_run_agenda_timed_deadline_and_scheduled_tasks_appear_in_time_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Timed deadline and timed scheduled tasks for the day should both appear in the timeline."""
    fixture_path = os.path.join(tmp_path, "agenda_deadline_and_scheduled.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(
            "* TODO Due today timed\n"
            "DEADLINE: <2025-01-15 Wed 09:00>\n\n"
            "* TODO Scheduled today timed\n"
            "SCHEDULED: <2025-01-15 Wed 10:00>\n",
        )

    args = _make_args([fixture_path], date="2025-01-15")
    monkeypatch.setattr(
        sys,
        "argv",
        ["org", "agenda", "--date", "2025-01-15", fixture_path],
    )
    output = _render_agenda_output(args)

    assert "Due today timed" in output
    assert "Scheduled today timed" in output
    assert output.index("09:00") < output.index("10:00")


def test_run_agenda_deadline_with_time_is_aligned_to_timetable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Timed deadlines should render in the current timeline rows."""
    fixture_path = os.path.join(tmp_path, "agenda_deadline_today_timed.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(
            "* TODO Timed due\nDEADLINE: <2025-01-15 Wed 09:30>\n",
        )

    args = _make_args([fixture_path], date="2025-01-15")
    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", "2025-01-15"])
    output = _render_agenda_output(args)

    assert "09:30" in output
    assert "Timed due" in output


def test_run_agenda_untimed_scheduled_omits_all_day_label(monkeypatch: pytest.MonkeyPatch) -> None:
    """Untimed scheduled rows should not include an all-day marker."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], date="2025-01-15")

    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", "2025-01-15"])
    output = _render_agenda_output(args)

    assert "all day" not in output


def test_run_agenda_default_view_shows_overdue_scheduled_and_deadline_tasks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Overdue tasks should not appear in the default timeline view."""
    pinned_now = _pin_agenda_now(monkeypatch)
    today = pinned_now.date()
    fixture_path = os.path.join(tmp_path, "agenda_overdue_section_order.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(
            "* TODO overdue sched\n"
            f"SCHEDULED: <{(today - timedelta(days=3)).isoformat()} Mon>\n\n"
            "* TODO overdue deadline\n"
            f"DEADLINE: <{(today - timedelta(days=2)).isoformat()} Tue>\n",
        )

    args = _make_args([fixture_path], date=today.isoformat())
    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", today.isoformat()])
    output = _render_agenda_output(args)

    assert "overdue sched" in output
    assert "overdue deadline" in output


def test_run_agenda_same_day_timed_tasks_are_ordered_by_time(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Timed tasks on the same day should appear in time order in the timeline."""
    pinned_now = _pin_agenda_now(monkeypatch)
    today = pinned_now.date()
    fixture_path = os.path.join(tmp_path, "agenda_ordering.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(
            "* TODO later task\n"
            f"SCHEDULED: <{today.isoformat()} Wed 14:00>\n\n"
            "* TODO earlier task\n"
            f"SCHEDULED: <{today.isoformat()} Wed 09:00>\n",
        )

    args = _make_args([fixture_path], date=today.isoformat())
    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", today.isoformat()])
    output = _render_agenda_output(args)

    assert output.index("earlier task") < output.index("later task")


def test_run_agenda_plain_view_rows_show_relative_day_labels(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Non-timeline agenda sections should show relative planning day labels."""
    fixture_path = os.path.join(tmp_path, "agenda_relative_plain_view.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(
            "* TODO Overdue scheduled\n"
            "SCHEDULED: <2025-01-13 Mon>\n\n"
            "* TODO Due today\n"
            "DEADLINE: <2025-01-15 Wed>\n\n"
            "* TODO Upcoming deadline\n"
            "DEADLINE: <2025-01-18 Sat>\n",
        )

    config = _app_config(
        agenda_views={
            "plain": org.config.app.AgendaViewConfig(
                name="plain",
                sections=[
                    org.config.app.AgendaSectionConfig(
                        name="Planning",
                        filter=".scheduled != null or .deadline != null",
                        order_by=None,
                        style="white",
                        timeline=False,
                    ),
                ],
            ),
        },
    )
    args = _make_args([fixture_path], date="2025-01-15", view="plain")

    monkeypatch.setattr(
        sys,
        "argv",
        ["org", "agenda", "--date", "2025-01-15", "--view", "plain", fixture_path],
    )
    output = _render_agenda_output_with_config(args, config)

    assert "2 days ago" in output
    assert "today" in output
    assert "in 3 days" in output


def test_build_view_day_model_plain_rows_choose_matching_planning_source() -> None:
    """Plain agenda rows should keep the planning source that matches their relative label."""
    root = org_parser.loads(
        "* TODO Deadline row\nDEADLINE: <2025-01-18 Sat>\n\n"
        "* TODO Scheduled row\nSCHEDULED: <2025-01-13 Mon>\n",
    )
    nodes = list(root)
    view = org.config.app.AgendaViewConfig(
        name="plain",
        sections=[
            org.config.app.AgendaSectionConfig(
                name="Planning",
                filter=".scheduled != null or .deadline != null",
                order_by=None,
                style="white",
                timeline=False,
            ),
        ],
    )
    day_model = ui.build_view_day_model(
        nodes,
        datetime(2025, 1, 15).date(),
        datetime(2025, 1, 15, 12, 0),
        AgendaViewContext(section_specs=_compile_view_section_specs(view), name=view.name),
        _make_args(["dummy.org"], date="2025-01-15"),
    )

    task_rows = [row for row in day_model.rows if row.kind == "task" and row.node is not None]
    task_row_details = []
    for row in task_rows:
        node = row.node
        assert node is not None
        task_row_details.append((node.title_text.strip(), row.time_text, row.source))
    assert task_row_details == [
        ("Deadline row", "in 3 days", "upcoming_deadline"),
        ("Scheduled row", "2 days ago", "overdue_scheduled"),
    ]


def test_run_agenda_timeline_view_appends_selected_untimed_tasks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Timeline sections should append selected untimed planning rows after the hour grid."""
    fixture_path = os.path.join(tmp_path, "agenda_timeline_untimed_view.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(
            "* TODO Timed task\n"
            "SCHEDULED: <2025-01-15 Wed 09:30>\n\n"
            "* TODO Untimed task\n"
            "SCHEDULED: <2025-01-15 Wed>\n",
        )

    config = _app_config(
        agenda_views={
            "timeline": org.config.app.AgendaViewConfig(
                name="timeline",
                sections=[
                    org.config.app.AgendaSectionConfig(
                        name="Agenda",
                        filter=".scheduled != null",
                        order_by=None,
                        style="white",
                        timeline=True,
                    ),
                ],
            ),
        },
    )
    args = _make_args([fixture_path], date="2025-01-15", view="timeline")

    monkeypatch.setattr(
        sys,
        "argv",
        ["org", "agenda", "--date", "2025-01-15", "--view", "timeline", fixture_path],
    )
    output = _render_agenda_output_with_config(args, config)

    assert "09:30" in output
    assert "Timed task" in output
    assert "today" in output
    assert "Untimed task" in output
    assert output.index("Timed task") < output.index("Untimed task")


def test_build_view_day_model_timeline_rows_append_untimed_with_deadline_precedence() -> None:
    """Timeline sections should append untimed rows after hour markers with deadline precedence."""
    root = org_parser.loads(
        "* TODO Timed row\nSCHEDULED: <2025-01-15 Wed 09:30>\n\n"
        "* TODO Untimed deadline row\nDEADLINE: <2025-01-18 Sat>\n\n"
        "* TODO Untimed scheduled row\nSCHEDULED: <2025-01-13 Mon>\n\n"
        "* TODO Both row\nSCHEDULED: <2025-01-14 Tue>\nDEADLINE: <2025-01-17 Fri>\n",
    )
    nodes = list(root)
    view = org.config.app.AgendaViewConfig(
        name="timeline",
        sections=[
            org.config.app.AgendaSectionConfig(
                name="Agenda",
                filter=".scheduled != null or .deadline != null",
                order_by=None,
                style="white",
                timeline=True,
            ),
        ],
    )
    day_model = ui.build_view_day_model(
        nodes,
        datetime(2025, 1, 15).date(),
        datetime(2025, 1, 15, 12, 0),
        AgendaViewContext(section_specs=_compile_view_section_specs(view), name=view.name),
        _make_args(["dummy.org"], date="2025-01-15"),
    )

    task_rows = [row for row in day_model.rows if row.kind == "task" and row.node is not None]
    task_row_details = []
    for row in task_rows:
        node = row.node
        assert node is not None
        task_row_details.append((node.title_text.strip(), row.time_text, row.source))
    assert task_row_details == [
        ("Timed row", "09:30", "scheduled"),
        ("Untimed deadline row", "in 3 days", "upcoming_deadline"),
        ("Untimed scheduled row", "2 days ago", "overdue_scheduled"),
        ("Both row", "in 2 days", "upcoming_deadline"),
    ]


def test_run_agenda_omits_inactive_planning_timestamps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Inactive scheduled/deadline timestamps should be ignored."""
    pinned_now = _pin_agenda_now(monkeypatch)
    today = pinned_now.date()
    fixture_path = os.path.join(tmp_path, "agenda_inactive.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(
            "* TODO inactive scheduled\n"
            f"SCHEDULED: [{today.isoformat()} Wed 09:30]\n\n"
            "* TODO inactive deadline\n"
            f"DEADLINE: [{(today + timedelta(days=3)).isoformat()} Sat]\n\n"
            "* DONE inactive repeat should still show\n"
            "SCHEDULED: <2025-01-01 Wed 11:00 +1d>\n"
            ":LOGBOOK:\n"
            f'- State "DONE" from "TODO" [{today.isoformat()} Wed 11:15]\n'
            ":END:\n",
        )

    args = _make_args([fixture_path], date=today.isoformat())
    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", today.isoformat()])
    output = _render_agenda_output(args)

    assert "inactive scheduled" not in output
    assert "inactive deadline" not in output
    assert "inactive repeat should still show" in output


def test_run_agenda_now_marker_renders_after_same_time_tasks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Now marker should render after tasks with the same minute."""
    fixture_path = os.path.join(tmp_path, "agenda_now_order.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(
            "* DONE Earlier task\n"
            "SCHEDULED: <2025-01-15 Wed 17:03>\n\n"
            "* DONE Same minute task\n"
            "SCHEDULED: <2025-01-15 Wed 17:04>\n\n"
            "* TODO Later task\n"
            "SCHEDULED: <2025-01-15 Wed 17:05>\n",
        )

    args = _make_args([fixture_path], date="2025-01-15")
    local_tz = local_now().tzinfo

    def current_now() -> datetime:
        return datetime(2025, 1, 15, 17, 4, 0, tzinfo=local_tz)

    monkeypatch.setattr(actions, "local_now", current_now)
    monkeypatch.setattr(ui, "local_now", current_now)
    monkeypatch.setattr("org.logic.time.local_now", current_now)
    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", "2025-01-15"])
    output = _render_agenda_output(args).replace("…", "")

    assert output.index("Same minute task") < output.index("------ NOW ------")
    assert output.index("------ NOW ------") < output.index("Later task")


def test_run_agenda_no_results_prints_message(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agenda should report no results after filters remove all nodes."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], filter_tags=["nomatch$"])

    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--filter-tag", "nomatch$"])
    agenda_command.run_agenda(args, org.config.app.AppConfig(config_path=".org-cli.yaml"))
    output = capsys.readouterr().out

    assert output.strip() == "No results"


def test_run_agenda_rejects_negative_offset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agenda should reject negative offsets."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], offset=-1)

    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--offset", "-1"])
    with pytest.raises(typer.BadParameter, match="--offset must be non-negative"):
        agenda_command.run_agenda(args, org.config.app.AppConfig(config_path=".org-cli.yaml"))


def test_run_agenda_rejects_negative_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agenda should reject negative limits."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], max_results=-1)

    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--limit", "-1"])
    with pytest.raises(typer.BadParameter, match="--limit must be non-negative"):
        agenda_command.run_agenda(args, org.config.app.AppConfig(config_path=".org-cli.yaml"))


def test_run_agenda_rejects_days_below_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agenda should reject --days values below one."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], days=0)

    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--days", "0"])
    with pytest.raises(typer.BadParameter, match="--days must be at least 1"):
        agenda_command.run_agenda(args, org.config.app.AppConfig(config_path=".org-cli.yaml"))


def test_run_agenda_invalid_date_raises_bad_parameter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agenda should validate --date format."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], date="2025/01/15")

    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", "2025/01/15"])
    with pytest.raises(typer.BadParameter, match="--date must be in one of these formats"):
        agenda_command.run_agenda(args, org.config.app.AppConfig(config_path=".org-cli.yaml"))


def test_parse_clock_duration_accepts_multiple_formats() -> None:
    """Clock duration parser should handle H:MM, minutes, and suffixed values."""
    assert duration_to_org_text(parse_clock_duration("1:30")) == "1:30"
    assert duration_to_org_text(parse_clock_duration("90")) == "1:30"
    assert duration_to_org_text(parse_clock_duration("2h")) == "2:00"
    assert duration_to_org_text(parse_clock_duration("45m")) == "0:45"


def test_advance_timestamp_by_repeater_moves_schedule_once() -> None:
    """Repeater-based advance should move schedule forward by one repeater step."""
    root = org_parser.loads("* TODO X\nSCHEDULED: <2025-01-15 Wed +1w>\n")
    heading = next(iter(root))
    scheduled = heading.scheduled
    assert scheduled is not None
    assert advance_timestamp_by_repeater(scheduled) is True
    assert str(scheduled).startswith("<2025-01-22")


def test_advance_timestamp_by_repeater_double_plus_advances_until_future(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """'++' repeater should advance repeatedly until timestamp is in the future."""
    timestamp = Timestamp.from_source("<2025-01-10 Fri ++1d>")
    monkeypatch.setattr(
        "org.logic.time.local_now",
        lambda: datetime(2025, 1, 15, 12, 0),
    )

    assert advance_timestamp_by_repeater(timestamp) is True
    assert str(timestamp).startswith("<2025-01-16")


def test_advance_timestamp_by_repeater_double_plus_hourly_uses_datetime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """'++' with hour unit should advance until datetime is after current time."""
    timestamp = Timestamp.from_source("<2025-01-15 Wed 09:00 ++1h>")
    monkeypatch.setattr(
        "org.logic.time.local_now",
        lambda: datetime(2025, 1, 15, 10, 30),
    )

    assert advance_timestamp_by_repeater(timestamp) is True
    assert str(timestamp).startswith("<2025-01-15 Wed 11:00")


def test_advance_timestamp_by_repeater_double_plus_always_shifts_at_least_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """'++' should still shift once when timestamp is already in the future."""
    timestamp = Timestamp.from_source("<2025-01-15 Wed 23:00 ++1d>")
    monkeypatch.setattr(
        "org.logic.time.local_now",
        lambda: datetime(2025, 1, 15, 10, 0),
    )

    assert advance_timestamp_by_repeater(timestamp) is True
    assert str(timestamp).startswith("<2025-01-16 Thu 23:00")


def test_advance_timestamp_by_repeater_dot_plus_uses_current_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """'.+' repeater should anchor at current day and then shift once by unit."""
    timestamp = Timestamp.from_source("<2025-01-10 Fri 09:30 .+2d>")
    monkeypatch.setattr(
        "org.logic.time.local_now",
        lambda: datetime(2025, 1, 15, 18, 45),
    )

    assert advance_timestamp_by_repeater(timestamp) is True
    assert str(timestamp).startswith("<2025-01-17 Fri 09:30")


def test_interactive_selection_can_land_on_hour_row_and_block_task_actions() -> None:
    """Selection should move onto hour rows and task-only actions should be blocked there."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], date="2025-01-15")
    root = org_parser.load(fixture_path)
    session = _make_session(args, list(root))

    hour_index = next(
        index
        for index, (day_index, row_index) in enumerate(session.row_locations)
        if session.day_models[day_index].rows[row_index].kind == "hour_marker"
    )
    session.selected_row_index = hour_index

    assert actions.selected_task_row(session) is None

    actions.apply_shift_date(session, day_delta=1)
    assert session.status_message == "Action available only on task rows"


def test_interactive_row_locations_skip_hidden_first_day_rows() -> None:
    """Interactive selection should not include the hidden first day header/spacer rows."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], date="2025-01-15")
    root = org_parser.load(fixture_path)
    session = _make_session(args, list(root))

    assert (0, 0) not in session.row_locations
    assert (0, 1) not in session.row_locations
    assert session.row_locations[0] == (0, 2)


def test_apply_state_change_uses_current_action_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """State transition repeat entry should use action-time wall clock, not cached session time."""
    args = _make_args(["dummy.org"], date="2025-01-15")
    root = org_parser.loads("* TODO Action time state change\nSCHEDULED: <2025-01-15 Wed 09:00>\n")
    heading = next(iter(root))
    session = _make_session(args, list(root))
    session.selected_row_index = next(
        index
        for index, (day_index, row_index) in enumerate(session.row_locations)
        if session.day_models[day_index].rows[row_index].kind == "task"
    )
    session.now = datetime(2025, 1, 15, 16, 30)
    action_now = datetime(2025, 1, 15, 17, 4, 33)
    monkeypatch.setattr(actions, "_save_document_changes", lambda _document: None)
    monkeypatch.setattr(actions, "_reload_session_nodes", lambda _session: None)
    monkeypatch.setattr(actions, "local_now", lambda: action_now)
    monkeypatch.setattr(
        actions,
        "refresh_session",
        lambda _session, _preserve_identity: None,
    )

    actions.apply_state_change_with_value(session, "DONE")

    assert heading.todo == "DONE"
    assert heading.repeats
    repeat_ts = heading.repeats[-1].timestamp.start
    assert repeat_ts.hour == 17
    assert repeat_ts.minute == 4


def test_apply_clock_entry_uses_current_action_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clock entry end time should use action-time wall clock, not cached session time."""
    args = _make_args(["dummy.org"], date="2025-01-15")
    root = org_parser.loads("* TODO Action time clock\nSCHEDULED: <2025-01-15 Wed 09:00>\n")
    heading = next(iter(root))
    session = _make_session(args, list(root))
    session.selected_row_index = next(
        index
        for index, (day_index, row_index) in enumerate(session.row_locations)
        if session.day_models[day_index].rows[row_index].kind == "task"
    )
    session.now = datetime(2025, 1, 15, 16, 30)
    action_now = datetime(2025, 1, 15, 17, 4, 33)
    monkeypatch.setattr(actions, "_save_document_changes", lambda _document: None)
    monkeypatch.setattr(actions, "_reload_session_nodes", lambda _session: None)
    monkeypatch.setattr(actions, "local_now", lambda: action_now)
    monkeypatch.setattr(
        actions,
        "refresh_session",
        lambda _session, _preserve_identity: None,
    )

    actions.apply_clock_entry_with_value(session, "30")

    assert heading.clock_entries
    timestamp = heading.clock_entries[-1].timestamp
    assert timestamp is not None
    assert timestamp.end is not None
    assert timestamp.end.hour == 17
    assert timestamp.end.minute == 4


def test_apply_refile_rejects_same_file_with_equivalent_path(
    tmp_path: os.PathLike[str],
) -> None:
    """Refile should treat equivalent path spellings as same-file destinations."""
    fixture_path = os.path.join(tmp_path, "agenda_refile_same.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write("* TODO Refile me\nSCHEDULED: <2025-01-15 Wed 09:00>\n")

    args = _make_args([fixture_path], date="2025-01-15")
    root = org_parser.load(fixture_path)
    session = _make_session(args, list(root))
    session.selected_row_index = next(
        index
        for index, (day_index, row_index) in enumerate(session.row_locations)
        if session.day_models[day_index].rows[row_index].kind == "task"
    )

    destination_alias = os.path.join(tmp_path, ".", "agenda_refile_same.org")
    actions.apply_refile_with_value(session, destination_alias)

    assert session.status_message == "Task already in destination file"
    with open(fixture_path, encoding="utf-8") as handle:
        content = handle.read()
    assert content.count("Refile me") == 1


def test_apply_refile_preserves_moved_task_locator(
    tmp_path: os.PathLike[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refile should preserve selection for the moved task in its destination file."""
    source_path = os.path.join(tmp_path, "agenda_refile_source.org")
    destination_path = os.path.join(tmp_path, "agenda_refile_destination.org")
    with open(source_path, "w", encoding="utf-8") as handle:
        handle.write(
            "* TODO Refile me\n"
            ":PROPERTIES:\n"
            ":ID: task-1\n"
            ":END:\n"
            "SCHEDULED: <2025-01-15 Wed 09:00>\n",
        )
    with open(destination_path, "w", encoding="utf-8") as handle:
        handle.write("* TODO Existing\n")

    args = _make_args([source_path], date="2025-01-15")
    root = org_parser.load(source_path)
    session = _make_session(args, list(root))
    heading = root.heading_by_id("task-1")
    assert heading is not None
    monkeypatch.setattr(
        actions,
        "selected_task_row",
        lambda _session: ui.AgendaRow(
            kind="task",
            day=datetime(2025, 1, 15).date(),
            node=heading,
            source="scheduled",
        ),
    )

    saved_documents: list[Document] = []
    refreshed: dict[str, object] = {}

    monkeypatch.setattr(actions, "_save_document_changes", saved_documents.append)
    monkeypatch.setattr(actions, "_reload_session_nodes", lambda _session: None)

    def _capture_refresh(
        current_session: actions.AgendaSession,
        preserve_identity: object,
    ) -> None:
        refreshed["session"] = current_session
        refreshed["identity"] = preserve_identity

    monkeypatch.setattr(actions, "refresh_session", _capture_refresh)

    actions.apply_refile_with_value(session, destination_path)

    assert refreshed["session"] is session
    assert refreshed["identity"] == heading_locator(heading)
    assert len(saved_documents) == 2
    assert session.status_message == f"Refiled task to {destination_path}"


def test_detail_org_block_includes_selected_heading_children() -> None:
    """Detail task text should include heading subtree including child headings."""
    root = org_parser.loads(
        "* TODO Parent task\nParent body\n** TODO Child task\nChild body\n",
    )
    heading = next(iter(root))
    output = detail_org_block(heading)

    assert "* TODO Parent task" in output
    assert "** TODO Child task" in output


def test_shift_planning_time_for_row_shifts_timed_scheduled_by_one_hour() -> None:
    """Shifting timed scheduled rows by hour should mutate scheduled timestamp time."""
    root = org_parser.loads("* TODO X\nSCHEDULED: <2025-01-15 Wed 10:30>\n")
    heading = next(iter(root))
    row = ui.AgendaRow(
        kind="task",
        day=datetime(2025, 1, 15).date(),
        node=heading,
        source="scheduled",
    )

    timestamp, status = actions.shift_planning_time_for_row(row, hour_delta=1)
    assert timestamp is not None
    assert status == "Shifted scheduled forward by 1 hour"
    assert str(timestamp).startswith("<2025-01-15 Wed 11:30")


def test_shift_planning_time_for_row_shifts_timed_deadline_by_one_hour() -> None:
    """Shifting timed deadline rows by hour should mutate deadline timestamp time."""
    root = org_parser.loads("* TODO X\nDEADLINE: <2025-01-15 Wed 10:30>\n")
    heading = next(iter(root))
    row = ui.AgendaRow(
        kind="task",
        day=datetime(2025, 1, 15).date(),
        node=heading,
        source="deadline",
    )

    timestamp, status = actions.shift_planning_time_for_row(row, hour_delta=1)
    assert timestamp is not None
    assert status == "Shifted deadline forward by 1 hour"
    assert str(timestamp).startswith("<2025-01-15 Wed 11:30")


def test_shift_planning_time_for_row_rejects_non_timed_rows() -> None:
    """Hour shifting should reject non-timed or non-planning row sources."""
    root = org_parser.loads("* TODO X\nSCHEDULED: <2025-01-15 Wed>\n")
    heading = next(iter(root))
    row = ui.AgendaRow(
        kind="task",
        day=datetime(2025, 1, 15).date(),
        node=heading,
        source="scheduled_untimed",
    )

    timestamp, status = actions.shift_planning_time_for_row(row, hour_delta=-1)
    assert timestamp is None
    assert status == "Time shifting is available only for timed scheduled/deadline rows"


def test_build_timeline_section_rows_preserves_timed_entry_sources() -> None:
    """Timeline rows should retain scheduled, deadline, and repeat sources."""
    root = org_parser.loads(
        """* TODO Scheduled
* TODO Deadline
* TODO Repeated
""",
    )
    assert root is not None
    scheduled, deadline, repeated = list(root)
    day = datetime(2025, 1, 15).date()
    entries = ui._ViewTimelineEntries(
        timed=[
            ui._TimedEntry(
                node=scheduled,
                when=datetime(2025, 1, 15, 9, 0),
                kind="scheduled",
            ),
            ui._TimedEntry(
                node=deadline,
                when=datetime(2025, 1, 15, 10, 0),
                kind="deadline",
            ),
            ui._TimedEntry(
                node=repeated,
                when=datetime(2025, 1, 15, 11, 0),
                kind="repeat",
            ),
        ],
        untimed=[],
    )

    rows = ui._build_timeline_section_rows(
        day,
        datetime(2025, 1, 15, 12, 0),
        entries,
        "Section",
        "",
    )

    task_sources = [row.source for row in rows if row.kind == "task"]
    assert task_sources == ["scheduled", "deadline", "repeat"]
