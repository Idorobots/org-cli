"""Tests for tui display helpers."""

from __future__ import annotations

from org.analyze import Group, TimeRange
from org.tui import (
    TopTasksSectionConfig,
    format_groups_section,
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
