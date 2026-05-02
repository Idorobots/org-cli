"""Tests for agenda command behavior and rendering."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from io import StringIO
from typing import TYPE_CHECKING

import org_parser
import pytest
import typer
from org_parser.time import Timestamp
from rich.console import Console

from org.commands import agenda as agenda_command
from org.commands import archive as archive_command
from org.commands import editor as editor_command
from org.commands.interactive_common import decode_escape_sequence, detail_org_block, local_now
from org.commands.tasks import capture as capture_command


if TYPE_CHECKING:
    from org_parser.document import Document, Heading


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


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
    today_date = local_now().date()
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
    today = local_now().date()
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

    today = local_now().date()
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
    today = local_now().date()
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
    today = local_now().date()
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
    today = local_now().date()
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
    local_tz = local_now().tzinfo
    monkeypatch.setattr(
        agenda_command,
        "local_now",
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
    assert decode_escape_sequence(b"\x1b") == "ESC"
    assert decode_escape_sequence(b"\x1b[A") == "UP"
    assert decode_escape_sequence(b"\x1b[B") == "DOWN"
    assert decode_escape_sequence(b"\x1b[C") == "RIGHT"
    assert decode_escape_sequence(b"\x1b[D") == "LEFT"
    assert decode_escape_sequence(b"\x1b[1;2A") == "S-UP"
    assert decode_escape_sequence(b"\x1b[1;2B") == "S-DOWN"
    assert decode_escape_sequence(b"\x1b[1;2C") == "S-RIGHT"
    assert decode_escape_sequence(b"\x1b[1;2D") == "S-LEFT"
    assert decode_escape_sequence(b"\x1b[<64;40;10M") == "WHEEL-UP"
    assert decode_escape_sequence(b"\x1b[<65;40;11M") == "WHEEL-DOWN"


def test_decode_escape_sequence_unknown_escape_is_not_exit() -> None:
    """Unknown escape sequences should not decode to ESC quit token."""
    key_name = decode_escape_sequence(b"\x1b[999~")
    assert key_name != "ESC"
    assert key_name.startswith("UNSUPPORTED-ESC:")


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


def test_advance_timestamp_by_repeater_double_plus_advances_until_future(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """'++' repeater should advance repeatedly until timestamp is in the future."""
    timestamp = Timestamp.from_source("<2025-01-10 Fri ++1d>")
    monkeypatch.setattr(
        agenda_command,
        "local_now",
        lambda: datetime(2025, 1, 15, 12, 0),
    )

    assert agenda_command._advance_timestamp_by_repeater(timestamp) is True
    assert str(timestamp).startswith("<2025-01-16")


def test_advance_timestamp_by_repeater_double_plus_hourly_uses_datetime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """'++' with hour unit should advance until datetime is after current time."""
    timestamp = Timestamp.from_source("<2025-01-15 Wed 09:00 ++1h>")
    monkeypatch.setattr(
        agenda_command,
        "local_now",
        lambda: datetime(2025, 1, 15, 10, 30),
    )

    assert agenda_command._advance_timestamp_by_repeater(timestamp) is True
    assert str(timestamp).startswith("<2025-01-15 Wed 11:00")


def test_advance_timestamp_by_repeater_double_plus_always_shifts_at_least_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """'++' should still shift once when timestamp is already in the future."""
    timestamp = Timestamp.from_source("<2025-01-15 Wed 23:00 ++1d>")
    monkeypatch.setattr(
        agenda_command,
        "local_now",
        lambda: datetime(2025, 1, 15, 10, 0),
    )

    assert agenda_command._advance_timestamp_by_repeater(timestamp) is True
    assert str(timestamp).startswith("<2025-01-16 Thu 23:00")


def test_advance_timestamp_by_repeater_dot_plus_uses_current_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """'.+' repeater should anchor at current day and then shift once by unit."""
    timestamp = Timestamp.from_source("<2025-01-10 Fri 09:30 .+2d>")
    monkeypatch.setattr(
        agenda_command,
        "local_now",
        lambda: datetime(2025, 1, 15, 18, 45),
    )

    assert agenda_command._advance_timestamp_by_repeater(timestamp) is True
    assert str(timestamp).startswith("<2025-01-17 Fri 09:30")


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


def test_handle_interactive_key_mouse_wheel_moves_selection() -> None:
    """Mouse wheel tokens should move selection same as down/up keys."""
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
    console = Console(file=StringIO(), force_terminal=False)

    start = session.selected_row_index
    assert agenda_command._handle_interactive_key(console, session, "WHEEL-DOWN") is True
    assert session.selected_row_index == (start + 1) % len(session.row_locations)

    assert agenda_command._handle_interactive_key(console, session, "WHEEL-UP") is True
    assert session.selected_row_index == start


def test_handle_interactive_key_refreshes_now_marker_when_minute_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Navigation should refresh session rows when local minute changes."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], date="2025-01-15")
    clock = {"value": datetime(2025, 1, 15, 10, 0)}
    monkeypatch.setattr("org.commands.agenda.local_now", lambda: clock["value"])
    root = org_parser.load(fixture_path)
    session = agenda_command._create_agenda_session(
        args,
        list(root),
        ["DONE"],
        ["TODO"],
        False,
    )
    console = Console(file=StringIO(), force_terminal=False)

    before = next(row.time_text for row in session.day_models[0].rows if row.kind == "now_marker")
    assert before == "10:00"

    clock["value"] = datetime(2025, 1, 15, 10, 1)
    assert agenda_command._handle_interactive_key(console, session, "DOWN") is True

    after = next(row.time_text for row in session.day_models[0].rows if row.kind == "now_marker")
    assert after == "10:01"


def test_interactive_renderable_refreshes_now_marker_without_keypress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Renderable rebuild should refresh now marker as local time advances."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], date="2025-01-15")
    clock = {"value": datetime(2025, 1, 15, 10, 0)}
    monkeypatch.setattr("org.commands.agenda.local_now", lambda: clock["value"])
    root = org_parser.load(fixture_path)
    session = agenda_command._create_agenda_session(
        args,
        list(root),
        ["DONE"],
        ["TODO"],
        False,
    )
    console = Console(file=StringIO(), force_terminal=False, width=120, height=24)

    _ = agenda_command._interactive_agenda_renderable(console, session)
    first_now = next(
        row.time_text for row in session.day_models[0].rows if row.kind == "now_marker"
    )
    assert first_now == "10:00"

    clock["value"] = datetime(2025, 1, 15, 10, 1)
    _ = agenda_command._interactive_agenda_renderable(console, session)
    second_now = next(
        row.time_text for row in session.day_models[0].rows if row.kind == "now_marker"
    )
    assert second_now == "10:01"


def test_handle_interactive_key_unsupported_key_sets_status_and_continues() -> None:
    """Unsupported key should set status message without exiting agenda loop."""
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
    console = Console(file=StringIO(), force_terminal=False)

    unsupported_key = "UNSUPPORTED-ESC:1b5b3939397e"
    assert agenda_command._handle_interactive_key(console, session, unsupported_key) is True
    assert session.status_message == f"Unsupported key: {unsupported_key}"


def test_apply_state_change_uses_current_action_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """State transition repeat entry should use action-time wall clock, not cached session time."""
    args = _make_args(["dummy.org"], date="2025-01-15")
    root = org_parser.loads("* TODO Action time state change\nSCHEDULED: <2025-01-15 Wed 09:00>\n")
    heading = next(iter(root))
    session = agenda_command._create_agenda_session(
        args,
        list(root),
        ["DONE"],
        ["TODO"],
        False,
    )
    session.selected_row_index = next(
        index
        for index, (day_index, row_index) in enumerate(session.row_locations)
        if session.day_models[day_index].rows[row_index].kind == "task"
    )
    session.now = datetime(2025, 1, 15, 16, 30)
    action_now = datetime(2025, 1, 15, 17, 4, 33)
    console = Console(file=StringIO(), force_terminal=False)

    monkeypatch.setattr("org.commands.agenda.local_now", lambda: action_now)
    monkeypatch.setattr(agenda_command, "_choose_state", lambda _console, _heading: "DONE")
    monkeypatch.setattr(agenda_command, "_save_document_changes", lambda _document: None)
    monkeypatch.setattr(agenda_command, "_reload_session_nodes", lambda _session: None)
    monkeypatch.setattr(
        agenda_command,
        "_refresh_session",
        lambda _session, _preserve_identity: None,
    )

    agenda_command._apply_state_change(console, session)

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
    session = agenda_command._create_agenda_session(
        args,
        list(root),
        ["DONE"],
        ["TODO"],
        False,
    )
    session.selected_row_index = next(
        index
        for index, (day_index, row_index) in enumerate(session.row_locations)
        if session.day_models[day_index].rows[row_index].kind == "task"
    )
    session.now = datetime(2025, 1, 15, 16, 30)
    action_now = datetime(2025, 1, 15, 17, 4, 33)
    console = Console(file=StringIO(), force_terminal=False)

    monkeypatch.setattr(console, "input", lambda _prompt: "30")
    monkeypatch.setattr("org.commands.agenda.local_now", lambda: action_now)
    monkeypatch.setattr(agenda_command, "_save_document_changes", lambda _document: None)
    monkeypatch.setattr(agenda_command, "_reload_session_nodes", lambda _session: None)
    monkeypatch.setattr(
        agenda_command,
        "_refresh_session",
        lambda _session, _preserve_identity: None,
    )

    agenda_command._apply_clock_entry(console, session)

    assert heading.clock_entries
    timestamp = heading.clock_entries[-1].timestamp
    assert timestamp is not None
    assert timestamp.end is not None
    assert timestamp.end.hour == 17
    assert timestamp.end.minute == 4


def test_apply_refile_rejects_same_file_with_equivalent_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: os.PathLike[str],
) -> None:
    """Refile should treat equivalent path spellings as same-file destinations."""
    fixture_path = os.path.join(tmp_path, "agenda_refile_same.org")
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write("* TODO Refile me\nSCHEDULED: <2025-01-15 Wed 09:00>\n")

    args = _make_args([fixture_path], date="2025-01-15")
    root = org_parser.load(fixture_path)
    session = agenda_command._create_agenda_session(
        args,
        list(root),
        ["DONE"],
        ["TODO"],
        False,
    )
    session.selected_row_index = next(
        index
        for index, (day_index, row_index) in enumerate(session.row_locations)
        if session.day_models[day_index].rows[row_index].kind == "task"
    )

    destination_alias = os.path.join(tmp_path, ".", "agenda_refile_same.org")
    console = Console(file=StringIO(), force_terminal=False)
    monkeypatch.setattr(console, "input", lambda _prompt: destination_alias)

    agenda_command._apply_refile(console, session)

    assert session.status_message == "Task already in destination file"
    with open(fixture_path, encoding="utf-8") as handle:
        content = handle.read()
    assert content.count("Refile me") == 1


def test_handle_interactive_key_enter_edits_selected_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enter should trigger external-editor editing on selected task row."""
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
    console = Console(file=StringIO(), force_terminal=False)

    task_index = next(
        index
        for index, (day_index, row_index) in enumerate(session.row_locations)
        if session.day_models[day_index].rows[row_index].kind == "task"
    )
    session.selected_row_index = task_index

    row = agenda_command._selected_task_row(session)
    assert row is not None
    assert row.node is not None

    def _fake_edit(heading: Heading) -> editor_command.HeadingEditResult:
        return editor_command.HeadingEditResult(heading=heading, changed=False)

    monkeypatch.setattr(agenda_command, "edit_heading_subtree_in_external_editor", _fake_edit)

    assert agenda_command._handle_interactive_key(console, session, "ENTER") is True
    assert session.status_message == "No changes."


def test_handle_interactive_key_enter_saves_original_document_after_changed_edit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Changed edit should save the selected task's original document."""
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
    console = Console(file=StringIO(), force_terminal=False)

    task_index = next(
        index
        for index, (day_index, row_index) in enumerate(session.row_locations)
        if session.day_models[day_index].rows[row_index].kind == "task"
    )
    session.selected_row_index = task_index

    row = agenda_command._selected_task_row(session)
    assert row is not None
    assert row.node is not None
    source_document = row.node.document
    detached_heading = next(iter(org_parser.loads("* TODO Updated\n")))

    def _fake_edit(_heading: Heading) -> editor_command.HeadingEditResult:
        return editor_command.HeadingEditResult(heading=detached_heading, changed=True)

    saved_documents: list[Document] = []

    def _capture_save(document: Document) -> None:
        saved_documents.append(document)

    monkeypatch.setattr(agenda_command, "edit_heading_subtree_in_external_editor", _fake_edit)
    monkeypatch.setattr(agenda_command, "_save_document_changes", _capture_save)
    monkeypatch.setattr(agenda_command, "_reload_session_nodes", lambda _session: None)
    monkeypatch.setattr(agenda_command, "_refresh_session", lambda _session, _identity: None)

    assert agenda_command._handle_interactive_key(console, session, "ENTER") is True
    assert session.status_message == "Task updated"
    assert saved_documents == [source_document]


def test_handle_interactive_key_dollar_archives_selected_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """$ should archive highlighted agenda task using shared archive helper."""
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
    console = Console(file=StringIO(), force_terminal=False)

    task_index = next(
        index
        for index, (day_index, row_index) in enumerate(session.row_locations)
        if session.day_models[day_index].rows[row_index].kind == "task"
    )
    session.selected_row_index = task_index

    def _fake_archive(
        heading: Heading,
        _cache: dict[str, Document],
    ) -> archive_command.ArchiveMoveResult:
        location = archive_command.ArchiveLocation(
            raw_spec="%s_archive::",
            file_path="tasks.org_archive",
            parent_title=None,
        )
        target = archive_command.ArchiveTarget(
            location=location,
            document=heading.document,
            parent_heading=None,
        )
        return archive_command.ArchiveMoveResult(
            heading=heading,
            target=target,
            source_document=heading.document,
            destination_document=heading.document,
        )

    monkeypatch.setattr(agenda_command, "archive_heading_subtree_and_save", _fake_archive)
    monkeypatch.setattr(agenda_command, "_reload_session_nodes", lambda _session: None)
    monkeypatch.setattr(agenda_command, "_refresh_session", lambda _session, _identity: None)

    assert agenda_command._handle_interactive_key(console, session, "$") is True
    assert session.status_message == "Task archived"


def test_handle_interactive_key_a_captures_and_schedules_on_timed_task_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """a on timed task row should capture and schedule with row-specific time."""
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
    console = Console(file=StringIO(), force_terminal=False)
    timed_task_index = next(
        index
        for index, (day_index, row_index) in enumerate(session.row_locations)
        if (
            session.day_models[day_index].rows[row_index].kind == "task"
            and session.day_models[day_index].rows[row_index].source
            in {"scheduled", "deadline_today", "repeat"}
            and ":" in session.day_models[day_index].rows[row_index].time_text
        )
    )
    session.selected_row_index = timed_task_index
    selected_row = agenda_command._selected_row(session)
    assert selected_row is not None
    expected_time = selected_row.time_text
    expected_timestamp = f"<2025-01-15 Wed {expected_time}>"
    captured_node = next(iter(org_parser.loads("* TODO Captured\n")))
    saved_documents: list[Document] = []
    reloaded: dict[str, object] = {}

    monkeypatch.setattr(
        agenda_command,
        "capture_task",
        lambda _args: capture_command.TasksCaptureResult(
            template_name="quick",
            heading=captured_node,
            document=captured_node.document,
        ),
    )

    def _capture_save(document: Document) -> None:
        saved_documents.append(document)

    monkeypatch.setattr(agenda_command, "_save_document_changes", _capture_save)
    monkeypatch.setattr(agenda_command, "_reload_session_nodes", lambda _session: None)

    def _fake_refresh(
        current_session: agenda_command._AgendaSession,
        preserve_identity: tuple[str, str, str, int | None] | None,
    ) -> None:
        reloaded["session"] = current_session
        reloaded["identity"] = preserve_identity

    monkeypatch.setattr(agenda_command, "_refresh_session", _fake_refresh)

    assert agenda_command._handle_interactive_key(console, session, "a") is True
    assert str(captured_node.scheduled) == expected_timestamp
    assert saved_documents == [captured_node.document]
    assert reloaded["session"] is session
    assert reloaded["identity"] == agenda_command._heading_identity(captured_node)
    assert session.status_message == f"Task captured and scheduled for {expected_timestamp}"


def test_handle_interactive_key_a_uses_now_marker_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """a on NOW marker row should capture and schedule using NOW row minute."""
    fixture_path = os.path.join(FIXTURES_DIR, "agenda_sample.org")
    args = _make_args([fixture_path], date="2025-01-15")
    local_tz = local_now().tzinfo
    monkeypatch.setattr(
        agenda_command,
        "local_now",
        lambda: datetime(2025, 1, 15, 17, 4, 0, tzinfo=local_tz),
    )
    root = org_parser.load(fixture_path)
    session = agenda_command._create_agenda_session(
        args,
        list(root),
        ["DONE"],
        ["TODO"],
        False,
    )
    console = Console(file=StringIO(), force_terminal=False)
    now_index = next(
        index
        for index, (day_index, row_index) in enumerate(session.row_locations)
        if session.day_models[day_index].rows[row_index].kind == "now_marker"
    )
    session.selected_row_index = now_index
    captured_node = next(iter(org_parser.loads("* TODO Captured\n")))

    monkeypatch.setattr(
        agenda_command,
        "capture_task",
        lambda _args: capture_command.TasksCaptureResult(
            template_name="quick",
            heading=captured_node,
            document=captured_node.document,
        ),
    )
    monkeypatch.setattr(agenda_command, "_save_document_changes", lambda _document: None)
    monkeypatch.setattr(agenda_command, "_reload_session_nodes", lambda _session: None)
    monkeypatch.setattr(agenda_command, "_refresh_session", lambda _session, _identity: None)

    assert agenda_command._handle_interactive_key(console, session, "a") is True
    assert str(captured_node.scheduled) == "<2025-01-15 Wed 17:04>"


def test_handle_interactive_key_a_on_non_timetable_row_reports_blocked() -> None:
    """a outside timetable rows should be blocked with a status message."""
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
    console = Console(file=StringIO(), force_terminal=False)
    blocked_index = next(
        index
        for index, (day_index, row_index) in enumerate(session.row_locations)
        if session.day_models[day_index].rows[row_index].kind == "section"
    )
    session.selected_row_index = blocked_index

    assert agenda_command._handle_interactive_key(console, session, "a") is True
    assert session.status_message == "Capture is available only on timetable time rows"


def test_handle_interactive_key_enter_on_non_task_row_stays_in_agenda() -> None:
    """Enter on non-task rows should keep agenda view and report status."""
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
    console = Console(file=StringIO(), force_terminal=False)

    hour_index = next(
        index
        for index, (day_index, row_index) in enumerate(session.row_locations)
        if session.day_models[day_index].rows[row_index].kind == "hour_marker"
    )
    session.selected_row_index = hour_index

    assert agenda_command._handle_interactive_key(console, session, "ENTER") is True
    assert session.status_message == "Action available only on task rows"


def test_handle_interactive_key_escape_quits_interactive_loop() -> None:
    """Esc should quit interactive agenda loop."""
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
    console = Console(file=StringIO(), force_terminal=False)

    assert agenda_command._handle_interactive_key(console, session, "ESC") is False


def test_detail_org_block_includes_selected_heading_children() -> None:
    """Detail task text should include heading subtree including child headings."""
    root = org_parser.loads(
        "* TODO Parent task\nParent body\n** TODO Child task\nChild body\n",
    )
    heading = next(iter(root))
    output = detail_org_block(heading)

    assert "* TODO Parent task" in output
    assert "** TODO Child task" in output


def test_interactive_renderable_footer_is_two_lines_without_status() -> None:
    """Interactive render should reserve exactly two footer lines when status is empty."""
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
    session.status_message = ""
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=False, width=300, height=24)

    console.print(agenda_command._interactive_agenda_renderable(console, session))
    lines = buffer.getvalue().splitlines()

    assert len(lines) == 24
    assert lines[-2].startswith("Lines ")
    assert "$ archive" in lines[-2]
    assert "q/Esc quit" in lines[-2]
    assert lines[-1] == ""


def test_interactive_renderable_footer_is_two_lines_with_status_on_narrow_width() -> None:
    """Interactive render should keep footer at two lines even on narrow terminals."""
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
    session.status_message = "Unsupported key: x"
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=False, width=80, height=24)

    console.print(agenda_command._interactive_agenda_renderable(console, session))
    lines = buffer.getvalue().splitlines()

    assert len(lines) == 24
    assert lines[-2].startswith("Lines ")
    assert lines[-1] == "Unsupported key: x"


def test_shift_planning_time_for_row_shifts_timed_scheduled_by_one_hour() -> None:
    """Shifting timed scheduled rows by hour should mutate scheduled timestamp time."""
    root = org_parser.loads("* TODO X\nSCHEDULED: <2025-01-15 Wed 10:30>\n")
    heading = next(iter(root))
    row = agenda_command._AgendaRow(
        kind="task",
        day=datetime(2025, 1, 15).date(),
        node=heading,
        source="scheduled",
    )

    timestamp, status = agenda_command._shift_planning_time_for_row(row, hour_delta=1)
    assert timestamp is not None
    assert status == "Shifted scheduled forward by 1 hour"
    assert str(timestamp).startswith("<2025-01-15 Wed 11:30")


def test_shift_planning_time_for_row_rejects_non_timed_rows() -> None:
    """Hour shifting should reject non-timed or non-planning row sources."""
    root = org_parser.loads("* TODO X\nSCHEDULED: <2025-01-15 Wed>\n")
    heading = next(iter(root))
    row = agenda_command._AgendaRow(
        kind="task",
        day=datetime(2025, 1, 15).date(),
        node=heading,
        source="scheduled_untimed",
    )

    timestamp, status = agenda_command._shift_planning_time_for_row(row, hour_delta=-1)
    assert timestamp is None
    assert status == "Time shifting is available only for timed scheduled/deadline rows"
