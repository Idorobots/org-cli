"""Tests for tui display helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from org.analyze import AnalysisResult, Group, Tag, TimeRange
from org.histogram import Histogram
from org.tui import (
    display_group_list,
    display_selected_items,
    display_task_summary,
    display_top_tasks,
)
from tests.conftest import node_from_org


def test_display_top_tasks_shows_filename(capsys: pytest.CaptureFixture[str]) -> None:
    """display_top_tasks should print a TASKS section when timestamps exist."""
    nodes = node_from_org(
        """
* DONE First task
CLOSED: [2025-01-01 Wed 10:00]

* DONE Second task
CLOSED: [2025-01-02 Thu 11:00]
"""
    )

    display_top_tasks(
        nodes, max_results=1, color_enabled=False, done_keys=["DONE"], todo_keys=["TODO"]
    )
    captured = capsys.readouterr().out

    assert "TASKS" in captured
    assert "<string>" in captured


def test_display_selected_items_shows_requested_tags(capsys: pytest.CaptureFixture[str]) -> None:
    """display_selected_items should show selected tags only."""
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

    display_selected_items(
        tags,
        ["beta"],
        (10, 0, 20, None, None, TimeRange(), set(), False),
    )
    captured = capsys.readouterr().out

    assert "beta" in captured
    assert "alpha" not in captured


def test_display_group_list_excludes_tags(capsys: pytest.CaptureFixture[str]) -> None:
    """display_group_list should omit excluded tags."""
    groups = [
        Group(
            tags=["alpha", "beta"],
            time_range=TimeRange(),
            total_tasks=2,
            avg_tasks_per_day=0.0,
            max_single_day_count=0,
        )
    ]

    display_group_list(
        groups,
        (10, 20, None, None, TimeRange(), {"beta"}, False),
    )
    captured = capsys.readouterr().out

    assert "alpha" in captured
    assert "beta" not in captured


def test_display_task_summary_renders_histograms(capsys: pytest.CaptureFixture[str]) -> None:
    """display_task_summary should print histogram sections."""
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
    args = SimpleNamespace(buckets=20)

    display_task_summary(result, args, (None, None, ["DONE"], ["TODO"], False))
    captured = capsys.readouterr().out

    assert "Task states:" in captured
    assert "Task categories:" in captured
    assert "Task occurrence by day of week:" in captured
