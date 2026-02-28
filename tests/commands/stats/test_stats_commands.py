"""Unit tests for stats command handlers."""

from __future__ import annotations

import os
import sys

import pytest
import typer

from org.analyze import AnalysisResult, Group, Tag, TimeRange
from org.commands.stats import groups as stats_groups
from org.commands.stats import summary as stats_summary
from org.commands.stats import tags as stats_tags
from org.commands.stats import tasks as stats_tasks
from org.histogram import Histogram


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures")


def make_summary_args(files: list[str], **overrides: object) -> stats_summary.SummaryArgs:
    """Build SummaryArgs with defaults and overrides."""
    args = stats_summary.SummaryArgs(
        files=files,
        config=".org-cli.json",
        exclude=None,
        mapping=None,
        mapping_inline=None,
        exclude_inline=None,
        todo_keys="TODO",
        done_keys="DONE",
        filter_gamify_exp_above=None,
        filter_gamify_exp_below=None,
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
        max_results=10,
        max_tags=5,
        use="tags",
        with_numeric_gamify_exp=False,
        with_gamify_category=False,
        with_tags_as_category=False,
        category_property="CATEGORY",
        max_relations=5,
        min_group_size=2,
        max_groups=5,
        buckets=50,
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
        filter_gamify_exp_above=None,
        filter_gamify_exp_below=None,
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
        max_results=10,
        max_tags=5,
        use="tags",
        show=None,
        with_numeric_gamify_exp=False,
        with_gamify_category=False,
        with_tags_as_category=False,
        category_property="CATEGORY",
        max_relations=5,
        min_group_size=2,
        max_groups=5,
        buckets=50,
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
        filter_gamify_exp_above=None,
        filter_gamify_exp_below=None,
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
        max_results=10,
        max_tags=5,
        use="tags",
        groups=None,
        with_numeric_gamify_exp=False,
        with_gamify_category=False,
        with_tags_as_category=False,
        category_property="CATEGORY",
        max_relations=5,
        min_group_size=2,
        max_groups=5,
        buckets=50,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def make_tasks_args(files: list[str], **overrides: object) -> stats_tasks.TasksArgs:
    """Build TasksArgs with defaults and overrides."""
    args = stats_tasks.TasksArgs(
        files=files,
        config=".org-cli.json",
        exclude=None,
        mapping=None,
        mapping_inline=None,
        exclude_inline=None,
        todo_keys="TODO",
        done_keys="DONE",
        filter_gamify_exp_above=None,
        filter_gamify_exp_below=None,
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
        max_results=10,
        max_tags=5,
        use="tags",
        with_numeric_gamify_exp=False,
        with_gamify_category=False,
        with_tags_as_category=False,
        category_property="CATEGORY",
        max_relations=5,
        min_group_size=2,
        max_groups=5,
        buckets=50,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_run_stats_summary_outputs_sections(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Summary command should output totals and sections."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_summary_args([fixture_path])

    monkeypatch.setattr(sys, "argv", ["org", "stats", "summary"])
    stats_summary.run_stats(args)
    captured = capsys.readouterr().out

    assert "Total tasks:" in captured
    assert "Task states:" in captured
    assert "TAGS" in captured


def test_run_stats_tasks_excludes_tag_sections(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tasks command should omit TAGS/GROUPS output."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_tasks_args([fixture_path])

    monkeypatch.setattr(sys, "argv", ["org", "stats", "tasks"])
    stats_tasks.run_stats_tasks(args)
    captured = capsys.readouterr().out

    assert "Task states:" in captured
    assert "TAGS" not in captured
    assert "GROUPS" not in captured


def test_run_stats_tasks_no_results(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tasks command should report when filters return no results."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_tasks_args([fixture_path], filter_tags=["nomatch$"])

    monkeypatch.setattr(sys, "argv", ["org", "stats", "tasks"])
    stats_tasks.run_stats_tasks(args)
    captured = capsys.readouterr().out

    assert "No results" in captured


def test_run_stats_summary_negative_max_results_raises_bad_parameter() -> None:
    """Summary command should reject negative max-results values."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_summary_args([fixture_path], max_results=-1)

    with pytest.raises(typer.BadParameter, match="--max-results must be non-negative"):
        stats_summary.run_stats(args)


def test_run_stats_tasks_negative_max_results_raises_bad_parameter() -> None:
    """Tasks command should reject negative max-results values."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_tasks_args([fixture_path], max_results=-1)

    with pytest.raises(typer.BadParameter, match="--max-results must be non-negative"):
        stats_tasks.run_stats_tasks(args)


def test_run_stats_tags_negative_max_results_raises_bad_parameter() -> None:
    """Tags command should reject negative max-results values."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_tags_args([fixture_path], max_results=-1)

    with pytest.raises(typer.BadParameter, match="--max-results must be non-negative"):
        stats_tags.run_stats_tags(args)


def test_run_stats_groups_negative_max_results_raises_bad_parameter() -> None:
    """Groups command should reject negative max-results values."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_groups_args([fixture_path], max_results=-1)

    with pytest.raises(typer.BadParameter, match="--max-results must be non-negative"):
        stats_groups.run_stats_groups(args)


def test_run_stats_tags_respects_show_filter(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tags command should filter to selected tags when --show is used."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_tags_args([fixture_path], show="Test")

    monkeypatch.setattr(sys, "argv", ["org", "stats", "tags", "--show", "Test"])
    stats_tags.run_stats_tags(args)
    captured = capsys.readouterr().out

    assert "Test" in captured
    assert "Debugging" not in captured


def test_run_stats_tags_show_heading(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tags command should normalize --show for heading usage."""
    fixture_path = os.path.join(FIXTURES_DIR, "simple.org")
    args = make_tags_args([fixture_path], use="heading", show="Simple")

    monkeypatch.setattr(sys, "argv", ["org", "stats", "tags", "--show", "Simple"])
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


def test_run_stats_summary_no_results(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Summary command should print No results when filtered away."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_summary_args([fixture_path], filter_tags=["nomatch$"])

    monkeypatch.setattr(sys, "argv", ["org", "stats", "summary"])
    stats_summary.run_stats(args)
    captured = capsys.readouterr().out

    assert "No results" in captured


def test_run_stats_summary_preprocessors(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Summary command should handle category preprocessors."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_summary_args(
        [fixture_path],
        with_gamify_category=True,
        with_tags_as_category=True,
    )

    monkeypatch.setattr(sys, "argv", ["org", "stats", "summary"])
    stats_summary.run_stats(args)
    captured = capsys.readouterr().out

    assert "Task categories:" in captured


def test_run_stats_summary_omits_groups_when_disabled(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Summary command should omit groups when max_groups is zero."""
    fixture_path = os.path.join(FIXTURES_DIR, "multiple_tags.org")
    args = make_summary_args([fixture_path], max_groups=0)

    monkeypatch.setattr(sys, "argv", ["org", "stats", "summary"])
    stats_summary.run_stats(args)
    captured = capsys.readouterr().out

    assert "GROUPS" not in captured


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
        task_categories=Histogram(values={"none": 2}),
        task_priorities=Histogram(values={"none": 2}),
        task_days=Histogram(values={}),
        timerange=TimeRange(),
        avg_tasks_per_day=0.0,
        max_single_day_count=0,
        max_repeat_count=0,
        tags={},
        tag_groups=[],
    )

    class Args:
        buckets = 20

    args = Args()

    output = stats_tasks.format_tasks_summary(result, args, (None, None, ["DONE"], ["TODO"], False))

    assert "Task states:" in output
    assert "Task categories:" in output
    assert "Task occurrence by day of week:" in output
