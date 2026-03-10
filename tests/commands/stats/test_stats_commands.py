"""Unit tests for stats command handlers."""

from __future__ import annotations

import os
import sys

import pytest
import typer

from org.analyze import AnalysisResult, Group, Tag, TimeRange
from org.commands.stats import all as stats_all_command
from org.commands.stats import groups as stats_groups
from org.commands.stats import summary as stats_summary_command
from org.commands.stats import tags as stats_tags
from org.histogram import Histogram


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures")


def make_stats_all_args(files: list[str], **overrides: object) -> stats_all_command.StatsAllArgs:
    """Build StatsAllArgs with defaults and overrides."""
    args = stats_all_command.StatsAllArgs(
        files=files,
        config=".org-cli.json",
        exclude=None,
        mapping=None,
        mapping_inline=None,
        exclude_inline=None,
        todo_keys="TODO",
        done_keys="DONE",
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
        width=None,
        max_results=10,
        max_tags=5,
        use="tags",
        with_tags_as_category=False,
        category_property="CATEGORY",
        max_relations=5,
        min_group_size=2,
        max_groups=5,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def make_tags_args(files: list[str], **overrides: object) -> stats_tags.TagsArgs:
    """Build TagsArgs with defaults and overrides."""
    args = stats_tags.TagsArgs(
        files=files,
        config=".org-cli.json",
        exclude=None,
        mapping=None,
        mapping_inline=None,
        exclude_inline=None,
        todo_keys="TODO",
        done_keys="DONE",
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
        width=None,
        max_results=10,
        max_tags=5,
        use="tags",
        tags=None,
        with_tags_as_category=False,
        category_property="CATEGORY",
        max_relations=5,
        min_group_size=2,
        max_groups=5,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def make_groups_args(files: list[str], **overrides: object) -> stats_groups.GroupsArgs:
    """Build GroupsArgs with defaults and overrides."""
    args = stats_groups.GroupsArgs(
        files=files,
        config=".org-cli.json",
        exclude=None,
        mapping=None,
        mapping_inline=None,
        exclude_inline=None,
        todo_keys="TODO",
        done_keys="DONE",
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
        width=None,
        max_results=10,
        max_tags=5,
        use="tags",
        groups=None,
        with_tags_as_category=False,
        category_property="CATEGORY",
        max_relations=5,
        min_group_size=2,
        max_groups=5,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def make_summary_args(files: list[str], **overrides: object) -> stats_summary_command.SummaryArgs:
    """Build SummaryArgs with defaults and overrides."""
    args = stats_summary_command.SummaryArgs(
        files=files,
        config=".org-cli.json",
        exclude=None,
        mapping=None,
        mapping_inline=None,
        exclude_inline=None,
        todo_keys="TODO",
        done_keys="DONE",
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
        width=None,
        max_results=10,
        with_tags_as_category=False,
        category_property="CATEGORY",
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_run_stats_all_outputs_sections(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Summary command should output totals and sections."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_stats_all_args([fixture_path])

    monkeypatch.setattr(sys, "argv", ["org", "stats", "all"])
    stats_all_command.run_stats(args)
    captured = capsys.readouterr().out

    assert "Total tasks:" in captured
    assert "Task states:" in captured
    assert "TAGS" in captured


def test_run_stats_summary_excludes_tag_sections(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Summary command should omit TAGS/GROUPS output."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_summary_args([fixture_path])

    monkeypatch.setattr(sys, "argv", ["org", "stats", "summary"])
    stats_summary_command.run_stats_summary(args)
    captured = capsys.readouterr().out

    assert "Task states:" in captured
    assert "TAGS" not in captured
    assert "GROUPS" not in captured


def test_run_stats_summary_no_results(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Summary command should report when filters return no results."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_summary_args([fixture_path], filter_tags=["nomatch$"])

    monkeypatch.setattr(sys, "argv", ["org", "stats", "summary"])
    stats_summary_command.run_stats_summary(args)
    captured = capsys.readouterr().out

    assert "No results" in captured


def test_run_stats_all_negative_max_results_raises_bad_parameter() -> None:
    """Summary command should reject negative max-results values."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_stats_all_args([fixture_path], max_results=-1)

    with pytest.raises(typer.BadParameter, match="--limit must be non-negative"):
        stats_all_command.run_stats(args)


def test_run_stats_summary_negative_max_results_raises_bad_parameter() -> None:
    """Summary command should reject negative max-results values."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_summary_args([fixture_path], max_results=-1)

    with pytest.raises(typer.BadParameter, match="--limit must be non-negative"):
        stats_summary_command.run_stats_summary(args)


def test_run_stats_tags_negative_max_results_raises_bad_parameter() -> None:
    """Tags command should reject negative max-results values."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_tags_args([fixture_path], max_results=-1)

    with pytest.raises(typer.BadParameter, match="--limit must be non-negative"):
        stats_tags.run_stats_tags(args)


def test_run_stats_groups_negative_max_results_raises_bad_parameter() -> None:
    """Groups command should reject negative max-results values."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_groups_args([fixture_path], max_results=-1)

    with pytest.raises(typer.BadParameter, match="--limit must be non-negative"):
        stats_groups.run_stats_groups(args)


def test_run_stats_tags_respects_tag_filter(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tags command should filter to selected tags when --tag is used."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_tags_args([fixture_path], tags=["Test"])

    monkeypatch.setattr(sys, "argv", ["org", "stats", "tags", "--tag", "Test"])
    stats_tags.run_stats_tags(args)
    captured = capsys.readouterr().out

    assert "Test" in captured
    assert "Debugging" not in captured


def test_run_stats_tags_tag_heading(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tags command should normalize --tag for heading usage."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")
    args = make_tags_args([fixture_path], use="heading", tags=["Simple"])

    monkeypatch.setattr(sys, "argv", ["org", "stats", "tags", "--tag", "Simple"])
    stats_tags.run_stats_tags(args)
    captured = capsys.readouterr().out

    assert "simple" in captured


def test_run_stats_groups_explicit_group(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Groups command should display explicit group selection."""
    fixture_path = os.path.join(FIXTURES_DIR, "tag_groups_test.org")
    args = make_groups_args([fixture_path], groups=["python,programming"])

    monkeypatch.setattr(sys, "argv", ["org", "stats", "groups", "--group", "python,programming"])
    stats_groups.run_stats_groups(args)
    captured = capsys.readouterr().out

    assert "python, programming" in captured


def test_run_stats_all_no_results(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Summary command should print No results when filtered away."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_stats_all_args([fixture_path], filter_tags=["nomatch$"])

    monkeypatch.setattr(sys, "argv", ["org", "stats", "all"])
    stats_all_command.run_stats(args)
    captured = capsys.readouterr().out

    assert "No results" in captured


def test_run_stats_all_category_preprocessor(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Summary command should handle tag-based category preprocessing."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_stats_all_args(
        [fixture_path],
        with_tags_as_category=True,
    )

    monkeypatch.setattr(sys, "argv", ["org", "stats", "all"])
    stats_all_command.run_stats(args)
    captured = capsys.readouterr().out

    assert "Task categories:" in captured


def test_run_stats_all_omits_groups_when_disabled(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Summary command should omit groups when max_groups is zero."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_stats_all_args([fixture_path], max_groups=0)

    monkeypatch.setattr(sys, "argv", ["org", "stats", "all"])
    stats_all_command.run_stats(args)
    captured = capsys.readouterr().out

    assert "GROUPS" not in captured


def test_run_stats_all_tasks_panel_grows_with_task_list(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: os.PathLike[str]
) -> None:
    """Summary TASKS panel should include all requested task rows in wide layout."""
    fixture_path = os.path.join(tmp_path, "many_tasks.org")
    lines = [
        f"* DONE Task-{index:02d}\nCLOSED: [2025-01-{(index % 28) + 1:02d} Wed 10:00]"
        for index in range(40)
    ]
    with open(fixture_path, "w", encoding="utf-8") as handle:
        handle.write("\n\n".join(lines) + "\n")

    args = make_stats_all_args([fixture_path], width=120, max_results=40, max_tags=0, max_groups=0)
    monkeypatch.setattr(sys, "argv", ["org", "stats", "all", "--width", "120", "--limit", "40"])
    stats_all_command.run_stats(args)
    captured = capsys.readouterr().out

    assert captured.count("Task-") == 40


def test_resolve_two_column_panel_content_width_accounts_for_panel_chrome() -> None:
    """Panel content width should subtract borders and horizontal padding."""
    assert stats_all_command._resolve_two_column_panel_content_width(80) == 36


def test_resolve_two_column_panel_content_width_respects_layout_floor() -> None:
    """Panel content width should respect the two-column minimum split."""
    assert stats_all_command._resolve_two_column_panel_content_width(40) == 21


def test_resolve_single_column_panel_content_width_accounts_for_panel_chrome() -> None:
    """Single-column panel width should subtract borders and horizontal padding."""
    assert stats_all_command._resolve_single_column_panel_content_width(80) == 76


def test_dedent_section_body_drops_leading_blank_and_title() -> None:
    """Section body normalization should remove leading blank line and title."""
    text = "\nTask states:\n  TODO 2\n"

    body = stats_all_command._dedent_section_body(text, drop_title=True)

    assert body == "TODO 2\n"


def test_dedent_section_body_handles_non_blank_first_line() -> None:
    """Section body normalization should still drop title when first line is non-blank."""
    text = "Task states:\n  TODO 2\n"

    body = stats_all_command._dedent_section_body(text, drop_title=True)

    assert body == "TODO 2\n"


def test_run_stats_all_narrow_layout_orders_sections_vertically(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Narrow viewport should render SUMMARY, TASKS, TAGS, GROUPS in order."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_stats_all_args([fixture_path], width=119, max_results=3, max_tags=3, max_groups=3)

    monkeypatch.setattr(sys, "argv", ["org", "stats", "all", "--width", "119"])
    stats_all_command.run_stats(args)
    captured = capsys.readouterr().out

    summary_index = captured.find("SUMMARY")
    tasks_index = captured.find("TASKS")
    tags_index = captured.find("TAGS")
    groups_index = captured.find("GROUPS")

    assert summary_index != -1
    assert tasks_index != -1
    assert tags_index != -1
    assert groups_index != -1
    assert summary_index < tasks_index < tags_index < groups_index


def test_stats_all_two_column_breakpoint() -> None:
    """Two-column layout should activate at width 120 and above."""
    assert stats_all_command._TWO_COLUMN_MIN_WIDTH == 120


def test_format_tags_shows_requested_tags() -> None:
    """format_tags should show selected tags only."""
    tags = {
        "alpha": Tag(
            name="alpha",
            total_tasks=3,
            avg_tasks_per_day=0.0,
            max_single_day_count=0,
            relations={},
            time_range=TimeRange(),
        ),
        "beta": Tag(
            name="beta",
            total_tasks=1,
            avg_tasks_per_day=0.0,
            max_single_day_count=0,
            relations={},
            time_range=TimeRange(),
        ),
    }

    output = stats_tags.format_tags(
        tags,
        ["beta"],
        (10, 0, 20, None, None, TimeRange(), set(), False),
    )

    assert "beta" in output
    assert "alpha" not in output


def test_format_group_list_excludes_tags() -> None:
    """format_group_list should omit excluded tags."""
    groups = [
        Group(
            tags=["alpha", "beta"],
            time_range=TimeRange(),
            total_tasks=2,
            avg_tasks_per_day=0.0,
            max_single_day_count=0,
        )
    ]

    output = stats_groups.format_group_list(
        groups,
        (10, 20, None, None, TimeRange(), {"beta"}, False),
    )

    assert "alpha" in output
    assert "beta" not in output


def test_format_tasks_summary_renders_histograms() -> None:
    """format_tasks_summary should include histogram sections."""
    result = AnalysisResult(
        total_tasks=2,
        unique_tasks=2,
        task_states=Histogram(values={"DONE": 1, "TODO": 1}),
        task_categories=Histogram(values={"null": 2}),
        task_priorities=Histogram(values={"null": 2}),
        task_days=Histogram(values={}),
        timerange=TimeRange(),
        avg_tasks_per_day=0.0,
        max_single_day_count=0,
        max_repeat_count=0,
        tags={},
        tag_groups=[],
    )

    output = stats_summary_command.format_tasks_summary(
        result, (None, None, ["DONE"], ["TODO"], False), 80
    )

    assert "Task states:" in output
    assert "Task categories:" in output
    assert "Task occurrence by day of week:" in output


def test_format_tasks_summary_orders_task_states_by_group_alphabetically() -> None:
    """Task states should be done-sorted, todo-sorted, then remaining-sorted."""
    result = AnalysisResult(
        total_tasks=6,
        unique_tasks=6,
        task_states=Histogram(
            values={
                "ZDONE": 1,
                "ADONE": 1,
                "ZTODO": 1,
                "ATODO": 1,
                "bbb": 1,
                "AAA": 1,
            }
        ),
        task_categories=Histogram(values={"null": 6}),
        task_priorities=Histogram(values={"null": 6}),
        task_days=Histogram(values={}),
        timerange=TimeRange(),
        avg_tasks_per_day=0.0,
        max_single_day_count=0,
        max_repeat_count=0,
        tags={},
        tag_groups=[],
    )

    output = stats_summary_command.format_tasks_summary(
        result,
        (None, None, ["ZDONE", "ADONE"], ["ZTODO", "ATODO"], False),
        80,
    )

    state_section = output.split("Task states:\n", maxsplit=1)[1].split(
        "\n\nTask priorities:", maxsplit=1
    )[0]
    state_names = [line.split("┊", maxsplit=1)[0].strip() for line in state_section.splitlines()]

    assert state_names == ["ADONE", "ZDONE", "ATODO", "ZTODO", "AAA", "bbb"]


def test_format_tasks_summary_omits_none_state_when_zero() -> None:
    """State 'null' should not be rendered when it has zero count."""
    result = AnalysisResult(
        total_tasks=2,
        unique_tasks=2,
        task_states=Histogram(values={"DONE": 2, "null": 0}),
        task_categories=Histogram(values={"null": 2}),
        task_priorities=Histogram(values={"null": 2}),
        task_days=Histogram(values={}),
        timerange=TimeRange(),
        avg_tasks_per_day=0.0,
        max_single_day_count=0,
        max_repeat_count=0,
        tags={},
        tag_groups=[],
    )

    output = stats_summary_command.format_tasks_summary(
        result, (None, None, ["DONE"], ["TODO"], False), 80
    )

    state_section = output.split("Task states:\n", maxsplit=1)[1].split(
        "\n\nTask priorities:", maxsplit=1
    )[0]
    assert "null" not in state_section


def test_format_tasks_summary_keeps_none_state_when_present() -> None:
    """State 'null' should be rendered when it has a positive count."""
    result = AnalysisResult(
        total_tasks=2,
        unique_tasks=2,
        task_states=Histogram(values={"DONE": 1, "null": 1}),
        task_categories=Histogram(values={"null": 2}),
        task_priorities=Histogram(values={"null": 2}),
        task_days=Histogram(values={}),
        timerange=TimeRange(),
        avg_tasks_per_day=0.0,
        max_single_day_count=0,
        max_repeat_count=0,
        tags={},
        tag_groups=[],
    )

    output = stats_summary_command.format_tasks_summary(
        result, (None, None, ["DONE"], ["TODO"], False), 80
    )

    state_section = output.split("Task states:\n", maxsplit=1)[1].split(
        "\n\nTask priorities:", maxsplit=1
    )[0]
    assert "null" in state_section
