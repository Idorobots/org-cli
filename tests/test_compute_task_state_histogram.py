"""Tests for the compute_task_state_histogram() function."""

from org.analyze import compute_task_state_histogram
from tests.conftest import node_from_org


def test_compute_task_state_histogram_empty_nodes() -> None:
    """Test with empty nodes list."""
    nodes = node_from_org("")

    histogram = compute_task_state_histogram(nodes)

    assert histogram.values.get("DONE", 0) == 0
    assert histogram.values.get("TODO", 0) == 0


def test_compute_task_state_histogram_single_done() -> None:
    """Test single DONE task."""
    nodes = node_from_org("* DONE Task\n")

    histogram = compute_task_state_histogram(nodes)

    assert histogram.values["DONE"] == 1


def test_compute_task_state_histogram_single_todo() -> None:
    """Test single TODO task."""
    nodes = node_from_org("* TODO Task\n")

    histogram = compute_task_state_histogram(nodes)

    assert histogram.values["TODO"] == 1


def test_compute_task_state_histogram_multiple_tasks() -> None:
    """Test multiple tasks with different states."""
    nodes = node_from_org("""
* TODO Task 1
* DONE Task 2
* TODO Task 3
""")

    histogram = compute_task_state_histogram(nodes)

    assert histogram.values["TODO"] == 2
    assert histogram.values["DONE"] == 1


def test_compute_task_state_histogram_repeated_tasks() -> None:
    """Test repeated tasks count individual states."""
    nodes = node_from_org("""
* TODO Task
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
- State "DONE"       from "TODO"       [2023-10-19 Thu 09:10]
- State "TODO"       from "DONE"       [2023-10-18 Wed 09:05]
:END:
""")

    histogram = compute_task_state_histogram(nodes)

    assert histogram.values["DONE"] == 2
    assert histogram.values["TODO"] == 1


def test_compute_task_state_histogram_no_state() -> None:
    """Test task without state maps to 'none'."""
    nodes = node_from_org("* Task without state\n")

    histogram = compute_task_state_histogram(nodes)

    assert histogram.values["none"] == 1


def test_compute_task_state_histogram_cancelled() -> None:
    """Test CANCELLED task state."""
    import orgparse

    content = """#+TODO: TODO | DONE CANCELLED

* CANCELLED Task
"""
    ns = orgparse.loads(content)
    nodes = list(ns[1:]) if ns else []

    histogram = compute_task_state_histogram(nodes)

    assert histogram.values["CANCELLED"] == 1


def test_compute_task_state_histogram_sum_equals_total() -> None:
    """Test that sum of state counts equals total tasks."""
    nodes = node_from_org("""
* TODO Task 1
* DONE Task 2
* TODO Task 3
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
- State "DONE"       from "TODO"       [2023-10-19 Thu 09:10]
:END:
""")

    histogram = compute_task_state_histogram(nodes)

    total_state_counts = sum(histogram.values.values())
    assert total_state_counts == 4
