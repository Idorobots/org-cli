"""Tests for the compute_task_stats() function."""

from orgstats.analyze import compute_task_stats
from tests.conftest import node_from_org


def test_compute_task_stats_empty_nodes() -> None:
    """Test with empty nodes list."""
    nodes = node_from_org("")

    total, max_repeat = compute_task_stats(nodes, ["DONE"])

    assert total == 0
    assert max_repeat == 0


def test_compute_task_stats_single_task() -> None:
    """Test single task without repeats."""
    nodes = node_from_org("* TODO Task\n")

    total, max_repeat = compute_task_stats(nodes, ["DONE"])

    assert total == 1
    assert max_repeat == 0


def test_compute_task_stats_single_done_task() -> None:
    """Test single DONE task."""
    nodes = node_from_org("* DONE Task\n")

    total, max_repeat = compute_task_stats(nodes, ["DONE"])

    assert total == 1
    assert max_repeat == 1


def test_compute_task_stats_multiple_tasks() -> None:
    """Test multiple tasks."""
    nodes = node_from_org("""
* TODO Task 1
* DONE Task 2
* TODO Task 3
""")

    total, max_repeat = compute_task_stats(nodes, ["DONE"])

    assert total == 3
    assert max_repeat == 1


def test_compute_task_stats_repeated_tasks() -> None:
    """Test repeated tasks count correctly."""
    nodes = node_from_org("""
* TODO Task
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
- State "DONE"       from "TODO"       [2023-10-19 Thu 09:10]
- State "TODO"       from "DONE"       [2023-10-18 Wed 09:05]
:END:
""")

    total, max_repeat = compute_task_stats(nodes, ["DONE"])

    assert total == 3
    assert max_repeat == 2


def test_compute_task_stats_max_repeat_count() -> None:
    """Test max_repeat_count tracks highest count."""
    nodes = node_from_org("""
* DONE Task 1

* TODO Task 2
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
- State "DONE"       from "TODO"       [2023-10-19 Thu 09:10]
:END:

* TODO Task 3
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-18 Wed 09:05]
- State "DONE"       from "TODO"       [2023-10-17 Tue 09:05]
- State "DONE"       from "TODO"       [2023-10-16 Mon 09:05]
- State "DONE"       from "TODO"       [2023-10-15 Sun 09:05]
:END:
""")

    total, max_repeat = compute_task_stats(nodes, ["DONE"])

    assert total == 7
    assert max_repeat == 4


def test_compute_task_stats_mixed_repeats() -> None:
    """Test mix of tasks with and without repeats."""
    nodes = node_from_org("""
* TODO Task 1

* DONE Task 2

* TODO Task 3
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
:END:
""")

    total, max_repeat = compute_task_stats(nodes, ["DONE"])

    assert total == 3
    assert max_repeat == 1
