"""Tests for statistics computation in analyze()."""

import orgparse

from orgstats.core import analyze


def test_avg_tasks_per_day_single_day() -> None:
    """Test average per day when all tasks completed on same day."""
    org_content = """
* DONE Task 1
CLOSED: [2024-01-15 Mon 10:00]

* DONE Task 2
CLOSED: [2024-01-15 Mon 14:00]

* DONE Task 3
CLOSED: [2024-01-15 Mon 18:00]
"""
    nodes = orgparse.loads(org_content)
    result = analyze(list(nodes[1:]), {}, "tags", 10)

    assert result.avg_tasks_per_day == 3.0


def test_avg_tasks_per_day_multiple_days() -> None:
    """Test average per day with tasks spread across multiple days."""
    org_content = """
* DONE Task 1
CLOSED: [2024-01-15 Mon 10:00]

* DONE Task 2
CLOSED: [2024-01-17 Wed 14:00]

* DONE Task 3
CLOSED: [2024-01-18 Thu 18:00]
"""
    nodes = orgparse.loads(org_content)
    result = analyze(list(nodes[1:]), {}, "tags", 10)

    assert result.avg_tasks_per_day == 3.0 / 4


def test_avg_tasks_per_day_includes_zero_days() -> None:
    """Test that average includes days with zero completions."""
    org_content = """
* DONE Task 1
CLOSED: [2024-01-15 Mon 10:00]

* DONE Task 2
CLOSED: [2024-01-20 Sat 14:00]
"""
    nodes = orgparse.loads(org_content)
    result = analyze(list(nodes[1:]), {}, "tags", 10)

    assert result.avg_tasks_per_day == 2.0 / 6


def test_avg_tasks_per_day_no_done_tasks() -> None:
    """Test average per day when no DONE tasks exist."""
    org_content = """
* TODO Task 1
SCHEDULED: <2024-01-15 Mon>

* TODO Task 2
SCHEDULED: <2024-01-20 Sat>
"""
    nodes = orgparse.loads(org_content)
    result = analyze(list(nodes[1:]), {}, "tags", 10)

    assert result.avg_tasks_per_day == 0.0


def test_max_single_day_count_clear_winner() -> None:
    """Test max single day count with clear winner."""
    org_content = """
* DONE Task 1
CLOSED: [2024-01-15 Mon 10:00]

* DONE Task 2
CLOSED: [2024-01-15 Mon 14:00]

* DONE Task 3
CLOSED: [2024-01-15 Mon 18:00]

* DONE Task 4
CLOSED: [2024-01-16 Tue 10:00]
"""
    nodes = orgparse.loads(org_content)
    result = analyze(list(nodes[1:]), {}, "tags", 10)

    assert result.max_single_day_count == 3


def test_max_single_day_count_with_ties() -> None:
    """Test max single day count when multiple days tie."""
    org_content = """
* DONE Task 1
CLOSED: [2024-01-15 Mon 10:00]

* DONE Task 2
CLOSED: [2024-01-15 Mon 14:00]

* DONE Task 3
CLOSED: [2024-01-16 Tue 10:00]

* DONE Task 4
CLOSED: [2024-01-16 Tue 14:00]
"""
    nodes = orgparse.loads(org_content)
    result = analyze(list(nodes[1:]), {}, "tags", 10)

    assert result.max_single_day_count == 2


def test_max_single_day_count_no_done_tasks() -> None:
    """Test max single day count when no DONE tasks exist."""
    org_content = """
* TODO Task 1
SCHEDULED: <2024-01-15 Mon>
"""
    nodes = orgparse.loads(org_content)
    result = analyze(list(nodes[1:]), {}, "tags", 10)

    assert result.max_single_day_count == 0


def test_max_repeat_count_no_repeats() -> None:
    """Test max repeat count when no tasks have repeats."""
    org_content = """
* DONE Task 1
CLOSED: [2024-01-15 Mon 10:00]

* DONE Task 2
CLOSED: [2024-01-16 Tue 14:00]
"""
    nodes = orgparse.loads(org_content)
    result = analyze(list(nodes[1:]), {}, "tags", 10)

    assert result.max_repeat_count == 1


def test_max_repeat_count_single_task_with_repeats() -> None:
    """Test max repeat count with single task having repeats."""
    org_content = """
* TODO Task with repeats
:LOGBOOK:
- State "DONE"       from "TODO"       [2024-01-10 Wed 10:00]
- State "DONE"       from "TODO"       [2024-01-15 Mon 11:00]
- State "DONE"       from "TODO"       [2024-01-20 Sat 12:00]
:END:
"""
    nodes = orgparse.loads(org_content)
    result = analyze(list(nodes[1:]), {}, "tags", 10)

    assert result.max_repeat_count == 3


def test_max_repeat_count_multiple_tasks_different_counts() -> None:
    """Test max repeat count with multiple tasks having different repeat counts."""
    org_content = """
* TODO Task 1 with 2 repeats
:LOGBOOK:
- State "DONE"       from "TODO"       [2024-01-10 Wed 10:00]
- State "DONE"       from "TODO"       [2024-01-15 Mon 11:00]
:END:

* TODO Task 2 with 5 repeats
:LOGBOOK:
- State "DONE"       from "TODO"       [2024-01-10 Wed 10:00]
- State "DONE"       from "TODO"       [2024-01-12 Fri 11:00]
- State "DONE"       from "TODO"       [2024-01-14 Sun 12:00]
- State "DONE"       from "TODO"       [2024-01-16 Tue 13:00]
- State "DONE"       from "TODO"       [2024-01-18 Thu 14:00]
:END:

* DONE Task 3 no repeats
CLOSED: [2024-01-20 Sat 15:00]
"""
    nodes = orgparse.loads(org_content)
    result = analyze(list(nodes[1:]), {}, "tags", 10)

    assert result.max_repeat_count == 5


def test_max_repeat_count_only_done_repeats() -> None:
    """Test max repeat count only counts DONE repeats, not other states."""
    org_content = """
* TODO Task with mixed states
:LOGBOOK:
- State "DONE"       from "TODO"       [2024-01-10 Wed 10:00]
- State "CANCELLED"  from "TODO"       [2024-01-12 Fri 11:00]
- State "DONE"       from "TODO"       [2024-01-15 Mon 12:00]
- State "TODO"       from "DONE"       [2024-01-16 Tue 13:00]
- State "DONE"       from "TODO"       [2024-01-18 Thu 14:00]
:END:
"""
    nodes = orgparse.loads(org_content)
    result = analyze(list(nodes[1:]), {}, "tags", 10)

    assert result.max_repeat_count == 3


def test_max_repeat_count_main_task_done_no_repeats() -> None:
    """Test max repeat count with main task DONE but no repeats."""
    org_content = """
* DONE Task 1
CLOSED: [2024-01-15 Mon 10:00]

* DONE Task 2
CLOSED: [2024-01-16 Tue 14:00]
"""
    nodes = orgparse.loads(org_content)
    result = analyze(list(nodes[1:]), {}, "tags", 10)

    assert result.max_repeat_count == 1


def test_max_repeat_count_main_done_with_repeats() -> None:
    """Test max repeat count uses repeats when main task is also DONE."""
    org_content = """
* DONE Task with main DONE and repeats
CLOSED: [2024-01-25 Thu 15:00]
:LOGBOOK:
- State "DONE"       from "TODO"       [2024-01-10 Wed 10:00]
- State "DONE"       from "TODO"       [2024-01-15 Mon 11:00]
- State "DONE"       from "TODO"       [2024-01-20 Sat 12:00]
:END:
"""
    nodes = orgparse.loads(org_content)
    result = analyze(list(nodes[1:]), {}, "tags", 10)

    assert result.max_repeat_count == 3


def test_statistics_all_zero_for_empty_nodes() -> None:
    """Test that all statistics are zero when no nodes provided."""
    result = analyze([], {}, "tags", 10)

    assert result.avg_tasks_per_day == 0.0
    assert result.max_single_day_count == 0
    assert result.max_repeat_count == 0


def test_avg_tasks_per_day_with_repeated_tasks() -> None:
    """Test average per day computation with repeated tasks."""
    org_content = """
* TODO Task with repeats spanning 5 days
:LOGBOOK:
- State "DONE"       from "TODO"       [2024-01-10 Wed 10:00]
- State "DONE"       from "TODO"       [2024-01-14 Sun 11:00]
:END:
"""
    nodes = orgparse.loads(org_content)
    result = analyze(list(nodes[1:]), {}, "tags", 10)

    assert result.avg_tasks_per_day == 2.0 / 5


def test_max_single_day_count_with_repeated_tasks() -> None:
    """Test max single day count with repeated tasks on same day."""
    org_content = """
* TODO Task with multiple completions same day
:LOGBOOK:
- State "DONE"       from "TODO"       [2024-01-15 Mon 10:00]
- State "DONE"       from "TODO"       [2024-01-15 Mon 14:00]
- State "DONE"       from "TODO"       [2024-01-15 Mon 18:00]
:END:
"""
    nodes = orgparse.loads(org_content)
    result = analyze(list(nodes[1:]), {}, "tags", 10)

    assert result.max_single_day_count == 3
