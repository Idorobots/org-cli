"""Tests for tui display helpers."""

from __future__ import annotations

from org.analyze import AnalysisResult, Group, Tag, TimeRange
from org.histogram import Histogram
from org.tui import (
    TopTasksSectionConfig,
    format_group_list,
    format_groups_section,
    format_selected_items,
    format_task_summary,
    format_top_tasks_section,
)
from tests.conftest import node_from_org


def test_format_top_tasks_section_shows_filename() -> None:
    """format_top_tasks_section should include a TASKS section."""
    nodes = node_from_org(
        """
* DONE First task
CLOSED: [2025-01-01 Wed 10:00]

* DONE Second task
CLOSED: [2025-01-02 Thu 11:00]
"""
    )

    output = format_top_tasks_section(
        nodes,
        TopTasksSectionConfig(
            max_results=1,
            color_enabled=False,
            done_keys=["DONE"],
            todo_keys=["TODO"],
            indent="",
        ),
    )

    assert "TASKS" in output
    assert "<string>" in output


def test_format_selected_items_shows_requested_tags() -> None:
    """format_selected_items should show selected tags only."""
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

    output = format_selected_items(
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

    output = format_group_list(
        groups,
        (10, 20, None, None, TimeRange(), {"beta"}, False),
    )

    assert "alpha" in output
    assert "beta" not in output


def test_format_groups_section_max_groups_zero_returns_empty() -> None:
    """format_groups_section should omit output when max_groups is zero."""
    groups = [
        Group(
            tags=["alpha", "beta"],
            time_range=TimeRange(),
            total_tasks=2,
            avg_tasks_per_day=0.0,
            max_single_day_count=0,
        )
    ]

    output = format_groups_section(
        groups,
        set(),
        (2, 20, None, None, TimeRange(), False),
        0,
    )

    assert output == ""


def test_format_task_summary_renders_histograms() -> None:
    """format_task_summary should include histogram sections."""
    result = AnalysisResult(
        total_tasks=3,
        task_states=Histogram(values={"DONE": 2, "TODO": 1}),
        task_categories=Histogram(values={"regular": 3}),
        task_days=Histogram(values={"Monday": 1, "unknown": 2}),
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

    output = format_task_summary(result, args, (None, None, ["DONE"], ["TODO"], False))

    assert "Task states:" in output
    assert "Task categories:" in output
    assert "Task occurrence by day of week:" in output
