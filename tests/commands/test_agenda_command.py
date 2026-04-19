"""Tests for agenda command behavior and rendering."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

import org_parser
import pytest
import typer

from org.commands import agenda as agenda_command


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def _make_args(files: list[str], **overrides: object) -> agenda_command.AgendaArgs:
    args = agenda_command.AgendaArgs(
        files=files,
        config=".org-cli.json",
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
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_run_agenda_renders_expected_sections(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agenda should render timetable and all section groups for the selected day."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], date="2025-01-15")
    args.max_results = sys.maxsize

    monkeypatch.setattr(
        sys,
        "argv",
        ["org", "agenda", "--date", "2025-01-15", fixture_path],
    )
    agenda_command.run_agenda(args)
    output = capsys.readouterr().out
    plain_output = output.replace("…", "")

    assert "2025-01-15" in plain_output
    assert "Timed agenda task" in plain_output
    assert "Repeated completion on day" in plain_output
    assert "Overdue scheduled" not in plain_output
    assert "Overdue deadlines" not in plain_output
    assert "Scheduled without specific time" in plain_output
    assert "Upcoming deadlines (30d)" not in plain_output
    assert "CATEGORY" in plain_output
    assert "TASK" in plain_output


def test_run_agenda_no_completed_hides_completed_and_repeats(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agenda should hide completed states and repeat completions with --no-completed."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], date="2025-01-15", no_completed=True)

    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", "2025-01-15", "--no-completed"])
    agenda_command.run_agenda(args)
    output = capsys.readouterr().out

    assert "Repeated completion on day" not in output
    assert "Completed one-off task" not in output


def test_run_agenda_no_overdue_hides_overdue_sections(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agenda should hide overdue sections and rows with --no-overdue."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], date="2025-01-15", no_overdue=True)

    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", "2025-01-15", "--no-overdue"])
    agenda_command.run_agenda(args)
    output = capsys.readouterr().out

    assert "Overdue scheduled" not in output
    assert "Overdue deadlines" not in output
    assert "Overdue scheduled task" not in output
    assert "Overdue deadline task" not in output


def test_run_agenda_no_upcoming_hides_upcoming_section(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agenda should hide upcoming deadline section with --no-upcoming."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], date="2025-01-15", no_upcoming=True)

    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", "2025-01-15", "--no-upcoming"])
    agenda_command.run_agenda(args)
    output = capsys.readouterr().out

    assert "Upcoming deadlines (30d)" not in output
    assert "Upcoming deadline task" not in output


def test_run_agenda_relative_sections_show_only_today(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Overdue/upcoming sections should render only for current-day agenda panes."""
    today_date = agenda_command._local_now().date()
    fixture_path = os.path.join(tmp_path, "agenda_today_relative.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(
            "* TODO Past scheduled\n"
            f"SCHEDULED: <{(today_date - timedelta(days=2)).isoformat()} Mon>\n\n"
            "* TODO Past deadline\n"
            f"DEADLINE: <{(today_date - timedelta(days=1)).isoformat()} Tue>\n\n"
            "* TODO Soon deadline\n"
            f"DEADLINE: <{(today_date + timedelta(days=3)).isoformat()} Fri>\n",
        )

    today = today_date.isoformat()
    args = _make_args([fixture_path], date=today)

    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", today])
    agenda_command.run_agenda(args)
    output = capsys.readouterr().out

    assert "Overdue scheduled" in output
    assert "Overdue deadlines" in output
    assert "Upcoming deadlines (30d)" in output


def test_run_agenda_days_renders_multiple_day_headers(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agenda should render one dated section per day in the requested range."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], date="2025-01-15", days=2)

    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", "2025-01-15", "--days", "2"])
    agenda_command.run_agenda(args)
    output = capsys.readouterr().out
    plain_output = output.replace("…", "")

    assert "2025-01-15" in plain_output
    assert "2025-01-16" in plain_output


def test_run_agenda_multi_day_shows_relative_sections_only_for_today(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Multi-day agenda should include overdue/upcoming only on today's day pane."""
    today = agenda_command._local_now().date()
    fixture_path = os.path.join(tmp_path, "agenda_multiday_relative.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(
            "* TODO alpha\n"
            f"SCHEDULED: <{(today - timedelta(days=4)).isoformat()} Mon>\n\n"
            "* TODO beta\n"
            f"DEADLINE: <{(today - timedelta(days=2)).isoformat()} Tue>\n\n"
            "* TODO gamma\n"
            f"DEADLINE: <{(today + timedelta(days=5)).isoformat()} Fri>\n",
        )

    today = agenda_command._local_now().date()
    start = (today - timedelta(days=1)).isoformat()
    args = _make_args([fixture_path], date=start, days=3)

    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", start, "--days", "3"])
    agenda_command.run_agenda(args)
    output = capsys.readouterr().out

    assert output.count("Overdue scheduled") == 1
    assert output.count("Overdue deadlines") == 1
    assert output.count("Upcoming deadlines (30d)") == 1


def test_run_agenda_single_day_default_omits_day_header(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Single-day agenda with default date should still render day header row."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path])

    monkeypatch.setattr(sys, "argv", ["org", "agenda"])
    agenda_command.run_agenda(args)
    output = capsys.readouterr().out
    plain_output = output.replace("…", "")

    assert "CATEGORY" in plain_output


def test_run_agenda_hides_repeat_prefix(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agenda should render repeated tasks without the REPEAT prefix."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], date="2025-01-15")

    monkeypatch.setattr(
        sys,
        "argv",
        ["org", "agenda", "--date", "2025-01-15", fixture_path],
    )
    agenda_command.run_agenda(args)
    output = capsys.readouterr().out

    assert "REPEAT " not in output


def test_run_agenda_repeat_row_uses_repeat_after_state(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Repeat rows should display repeat.after state, not current heading state."""
    fixture_path = os.path.join(tmp_path, "agenda_repeat_state.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(
            "* TODO Reopened repeat task\n"
            "SCHEDULED: <2025-01-01 Wed 11:00 +1d>\n"
            ":LOGBOOK:\n"
            '- State "DONE"       from "TODO"       [2025-01-15 Wed 11:15]\n'
            '- State "TODO"       from "DONE"       [2025-01-16 Thu 11:15]\n'
            ":END:\n",
        )

    args = _make_args([fixture_path], date="2025-01-15")
    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", "2025-01-15"])
    agenda_command.run_agenda(args)
    output = capsys.readouterr().out

    assert "DONE Reopened repeat task" in output
    assert "TODO Reopened repeat task" not in output


def test_run_agenda_excludes_completed_untimed_scheduled(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Untimed scheduled section should omit completed tasks."""
    fixture_path = os.path.join(tmp_path, "agenda_untimed_done.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(
            "* DONE Completed untimed\n"
            "SCHEDULED: <2025-01-15 Wed>\n\n"
            "* TODO Active untimed\n"
            "SCHEDULED: <2025-01-15 Wed>\n",
        )

    args = _make_args([fixture_path], date="2025-01-15")
    monkeypatch.setattr(
        sys,
        "argv",
        ["org", "agenda", "--date", "2025-01-15", fixture_path],
    )
    agenda_command.run_agenda(args)
    output = capsys.readouterr().out

    assert "Active untimed" in output
    assert "Completed untimed" not in output


def test_run_agenda_shows_deadline_untimed_section_before_scheduled_untimed(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Untimed deadlines for the selected day should appear before untimed scheduled tasks."""
    fixture_path = os.path.join(tmp_path, "agenda_deadline_today_untimed.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(
            "* TODO Due today\n"
            "DEADLINE: <2025-01-15 Wed>\n\n"
            "* TODO Scheduled today\n"
            "SCHEDULED: <2025-01-15 Wed>\n",
        )

    args = _make_args([fixture_path], date="2025-01-15")
    monkeypatch.setattr(
        sys,
        "argv",
        ["org", "agenda", "--date", "2025-01-15", fixture_path],
    )
    agenda_command.run_agenda(args)
    output = capsys.readouterr().out

    assert "Deadlines without specific time" in output
    assert output.index("Deadlines without specific time") < output.index(
        "Scheduled without specific time",
    )
    assert output.index("Due today") < output.index("Scheduled today")


def test_run_agenda_deadline_with_time_is_aligned_to_timetable(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Deadline with specific time on selected day should be in hourly timetable rows."""
    fixture_path = os.path.join(tmp_path, "agenda_deadline_today_timed.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(
            "* TODO Timed due\nDEADLINE: <2025-01-15 Wed 09:30>\n",
        )

    args = _make_args([fixture_path], date="2025-01-15")
    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", "2025-01-15"])
    agenda_command.run_agenda(args)
    output = capsys.readouterr().out

    assert "09:30" in output
    assert "Timed due" in output
    assert "Deadlines without specific time" not in output


def test_run_agenda_untimed_scheduled_omits_all_day_label(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Untimed scheduled rows should not include an all-day marker."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], date="2025-01-15")

    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", "2025-01-15"])
    agenda_command.run_agenda(args)
    output = capsys.readouterr().out

    assert "all day" not in output


def test_run_agenda_overdue_deadlines_precede_overdue_scheduled(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Overdue deadlines section should appear before overdue scheduled section."""
    today = agenda_command._local_now().date()
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
    agenda_command.run_agenda(args)
    output = capsys.readouterr().out

    assert output.index("Overdue deadlines") < output.index("Overdue scheduled")


def test_run_agenda_orders_overdue_and_upcoming_by_age(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Overdue should be oldest-first and upcoming should be soonest-first."""
    today = agenda_command._local_now().date()
    fixture_path = os.path.join(tmp_path, "agenda_ordering.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write(
            "* TODO old overdue\n"
            f"SCHEDULED: <{(today - timedelta(days=10)).isoformat()} Fri>\n\n"
            "* TODO newer overdue\n"
            f"SCHEDULED: <{(today - timedelta(days=2)).isoformat()} Fri>\n\n"
            "* TODO later upcoming\n"
            f"DEADLINE: <{(today + timedelta(days=7)).isoformat()} Fri>\n\n"
            "* TODO sooner upcoming\n"
            f"DEADLINE: <{(today + timedelta(days=2)).isoformat()} Fri>\n",
        )

    args = _make_args([fixture_path], date=today.isoformat())
    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", today.isoformat()])
    agenda_command.run_agenda(args)
    output = capsys.readouterr().out

    assert output.index("old overdue") < output.index("newer overdue")
    assert output.index("sooner upcoming") < output.index("later upcoming")


def test_run_agenda_omits_inactive_planning_timestamps(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Inactive scheduled/deadline timestamps should be ignored."""
    today = agenda_command._local_now().date()
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
    agenda_command.run_agenda(args)
    output = capsys.readouterr().out

    assert "inactive scheduled" not in output
    assert "inactive deadline" not in output
    assert "inactive repeat should still show" in output


def test_run_agenda_now_marker_renders_after_same_time_tasks(
    capsys: pytest.CaptureFixture[str],
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
    local_tz = agenda_command._local_now().tzinfo
    monkeypatch.setattr(
        agenda_command,
        "_local_now",
        lambda: datetime(2025, 1, 15, 17, 4, 0, tzinfo=local_tz),
    )
    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", "2025-01-15"])
    agenda_command.run_agenda(args)
    output = capsys.readouterr().out.replace("…", "")

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
    agenda_command.run_agenda(args)
    output = capsys.readouterr().out

    assert output.strip() == "No results"


def test_run_agenda_rejects_negative_offset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agenda should reject negative offsets."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], offset=-1)

    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--offset", "-1"])
    with pytest.raises(typer.BadParameter, match="--offset must be non-negative"):
        agenda_command.run_agenda(args)


def test_run_agenda_rejects_negative_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agenda should reject negative limits."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], max_results=-1)

    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--limit", "-1"])
    with pytest.raises(typer.BadParameter, match="--limit must be non-negative"):
        agenda_command.run_agenda(args)


def test_run_agenda_rejects_days_below_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agenda should reject --days values below one."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], days=0)

    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--days", "0"])
    with pytest.raises(typer.BadParameter, match="--days must be at least 1"):
        agenda_command.run_agenda(args)


def test_run_agenda_invalid_date_raises_bad_parameter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agenda should validate --date format."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], date="2025/01/15")

    monkeypatch.setattr(sys, "argv", ["org", "agenda", "--date", "2025/01/15"])
    with pytest.raises(typer.BadParameter, match="--date must be in one of these formats"):
        agenda_command.run_agenda(args)


def test_decode_escape_sequence_supports_arrows() -> None:
    """Escape-sequence decoder should map plain and shifted arrow keys."""
    assert agenda_command._decode_escape_sequence(b"\x1b") == "ESC"
    assert agenda_command._decode_escape_sequence(b"\x1b[A") == "UP"
    assert agenda_command._decode_escape_sequence(b"\x1b[B") == "DOWN"
    assert agenda_command._decode_escape_sequence(b"\x1b[C") == "RIGHT"
    assert agenda_command._decode_escape_sequence(b"\x1b[D") == "LEFT"
    assert agenda_command._decode_escape_sequence(b"\x1b[1;2C") == "S-RIGHT"
    assert agenda_command._decode_escape_sequence(b"\x1b[1;2D") == "S-LEFT"


def test_parse_clock_duration_accepts_multiple_formats() -> None:
    """Clock duration parser should handle H:MM, minutes, and suffixed values."""
    assert (
        agenda_command._duration_to_org_text(agenda_command._parse_clock_duration("1:30")) == "1:30"
    )
    assert (
        agenda_command._duration_to_org_text(agenda_command._parse_clock_duration("90")) == "1:30"
    )
    assert (
        agenda_command._duration_to_org_text(agenda_command._parse_clock_duration("2h")) == "2:00"
    )
    assert (
        agenda_command._duration_to_org_text(agenda_command._parse_clock_duration("45m")) == "0:45"
    )


def test_advance_timestamp_by_repeater_moves_schedule_once() -> None:
    """Repeater-based advance should move schedule forward by one repeater step."""
    root = org_parser.loads("* TODO X\nSCHEDULED: <2025-01-15 Wed +1w>\n")
    heading = next(iter(root))
    scheduled = heading.scheduled
    assert scheduled is not None
    assert agenda_command._advance_timestamp_by_repeater(scheduled) is True
    assert str(scheduled).startswith("<2025-01-22")


def test_interactive_selection_can_land_on_hour_row_and_block_task_actions() -> None:
    """Selection should move onto hour rows and task-only actions should be blocked there."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], date="2025-01-15")
    root = org_parser.load(fixture_path)
    session = agenda_command._create_agenda_session(
        args,
        list(root),
        ["DONE"],
        ["TODO"],
        False,
    )

    hour_index = next(
        index
        for index, (day_index, row_index) in enumerate(session.row_locations)
        if session.day_models[day_index].rows[row_index].kind == "hour_marker"
    )
    session.selected_row_index = hour_index

    assert agenda_command._selected_task_row(session) is None

    agenda_command._apply_shift_date(session, day_delta=1)
    assert session.status_message == "Action available only on task rows"
