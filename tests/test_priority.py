"""Tests for priority histogram and display functionality."""

from __future__ import annotations

from org.analyze import compute_priority_histogram
from org.tui import TaskLineConfig, format_task_line
from tests.conftest import node_from_org


def test_compute_priority_histogram_with_priorities() -> None:
    """compute_priority_histogram should count tasks by priority."""
    nodes = node_from_org(
        """
* TODO [#A] Task A

* TODO [#B] Task B

* TODO [#A] Another A
"""
    )

    histogram = compute_priority_histogram(nodes)

    assert histogram.values.get("A") == 2
    assert histogram.values.get("B") == 1


def test_compute_priority_histogram_without_priorities() -> None:
    """compute_priority_histogram should count tasks without priorities as none."""
    nodes = node_from_org(
        """
* TODO Task without priority

* TODO Another task
"""
    )

    histogram = compute_priority_histogram(nodes)

    assert histogram.values.get("none") == 2


def test_format_task_line_with_priority() -> None:
    """format_task_line should display priority after todo state."""
    nodes = node_from_org(
        """
* TODO [#A] Task with priority
"""
    )

    line = format_task_line(
        nodes[0],
        TaskLineConfig(
            color_enabled=False,
            done_keys=["DONE"],
            todo_keys=["TODO"],
            buckets=0,
        ),
    )

    assert "[#A]" in line
    assert "TODO" in line


def test_format_task_line_without_priority() -> None:
    """format_task_line should not display priority when absent."""
    nodes = node_from_org(
        """
* TODO Task without priority
"""
    )

    line = format_task_line(
        nodes[0],
        TaskLineConfig(
            color_enabled=False,
            done_keys=["DONE"],
            todo_keys=["TODO"],
            buckets=0,
        ),
    )

    assert "[#" not in line
    assert "TODO" in line


def test_format_task_line_with_tags() -> None:
    """format_task_line should display tags aligned to right."""
    nodes = node_from_org(
        """
* TODO Task with tags  :TAG1:TAG2:
"""
    )

    line = format_task_line(
        nodes[0],
        TaskLineConfig(
            color_enabled=False,
            done_keys=["DONE"],
            todo_keys=["TODO"],
            buckets=80,
        ),
    )

    assert ":TAG1:TAG2:" in line
    assert "TODO" in line


def test_format_task_line_without_tags() -> None:
    """format_task_line should work without tags."""
    nodes = node_from_org(
        """
* TODO Task without tags
"""
    )

    line = format_task_line(
        nodes[0],
        TaskLineConfig(
            color_enabled=False,
            done_keys=["DONE"],
            todo_keys=["TODO"],
            buckets=80,
        ),
    )

    assert "TODO" in line
    assert ":" not in line or "<string>:" in line


def test_format_task_line_with_priority_and_tags() -> None:
    """format_task_line should display both priority and tags."""
    nodes = node_from_org(
        """
* TODO [#B] Task with both  :TAG1:
"""
    )

    line = format_task_line(
        nodes[0],
        TaskLineConfig(
            color_enabled=False,
            done_keys=["DONE"],
            todo_keys=["TODO"],
            buckets=80,
        ),
    )

    assert "[#B]" in line
    assert ":TAG1:" in line
    assert "TODO" in line
