"""Tests for global timerange computation in analyze()."""

from datetime import datetime

import orgparse

from orgstats.analyze import analyze


def test_global_timerange_includes_todo_tasks() -> None:
    """Test that global timerange includes TODO tasks."""
    org_content = """
* TODO Task 1
CLOSED: [2024-01-15 Mon 10:00]
:LOGBOOK:
- State "TODO"       from "DONE"       [2024-01-15 Mon 10:00]
:END:
"""
    nodes = orgparse.loads(org_content)
    result = analyze(list(nodes[1:]), {}, "tags", 10)

    assert result.timerange.earliest is not None
    assert result.timerange.latest is not None
    assert len(result.timerange.timeline) > 0


def test_global_timerange_single_done_task() -> None:
    """Test global timerange with a single DONE task."""
    org_content = """
* DONE Task 1
CLOSED: [2024-01-15 Mon 10:00]
"""
    nodes = orgparse.loads(org_content)
    result = analyze(list(nodes[1:]), {}, "tags", 10)

    assert result.timerange.earliest == datetime(2024, 1, 15, 10, 0)
    assert result.timerange.latest == datetime(2024, 1, 15, 10, 0)
    assert len(result.timerange.timeline) == 1


def test_global_timerange_multiple_done_tasks() -> None:
    """Test global timerange with multiple DONE tasks."""
    org_content = """
* DONE Task 1
CLOSED: [2024-01-15 Mon 10:00]

* DONE Task 2
CLOSED: [2024-03-20 Wed 14:30]

* DONE Task 3
CLOSED: [2024-02-10 Sat 09:00]
"""
    nodes = orgparse.loads(org_content)
    result = analyze(list(nodes[1:]), {}, "tags", 10)

    assert result.timerange.earliest == datetime(2024, 1, 15, 10, 0)
    assert result.timerange.latest == datetime(2024, 3, 20, 14, 30)
    assert len(result.timerange.timeline) == 3


def test_global_timerange_includes_all_tasks() -> None:
    """Test that global timerange includes all tasks regardless of state."""
    org_content = """
* TODO Task 1
CLOSED: [2024-01-15 Mon 10:00]

* CANCELLED Task 2
CLOSED: [2024-01-20 Sat 14:00]

* DONE Task 3
CLOSED: [2024-01-25 Thu 09:00]
"""
    nodes = orgparse.loads(org_content)
    result = analyze(list(nodes[1:]), {}, "tags", 10)

    assert result.timerange.earliest == datetime(2024, 1, 15, 10, 0)
    assert result.timerange.latest == datetime(2024, 1, 25, 9, 0)
    assert len(result.timerange.timeline) == 3


def test_global_timerange_with_done_repeated_tasks() -> None:
    """Test that global timerange includes DONE repeated tasks."""
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

    assert result.timerange.earliest == datetime(2024, 1, 10, 10, 0)
    assert result.timerange.latest == datetime(2024, 1, 20, 12, 0)
    assert len(result.timerange.timeline) == 3


def test_global_timerange_with_mixed_repeated_tasks() -> None:
    """Test global timerange with all repeated tasks regardless of state."""
    org_content = """
* TODO Task with mixed repeats
:LOGBOOK:
- State "DONE"       from "TODO"       [2024-01-10 Wed 10:00]
- State "CANCELLED"  from "TODO"       [2024-01-12 Fri 11:00]
- State "DONE"       from "TODO"       [2024-01-15 Mon 12:00]
:END:
"""
    nodes = orgparse.loads(org_content)
    result = analyze(list(nodes[1:]), {}, "tags", 10)

    assert result.timerange.earliest == datetime(2024, 1, 10, 10, 0)
    assert result.timerange.latest == datetime(2024, 1, 15, 12, 0)
    assert len(result.timerange.timeline) == 3


def test_global_timerange_combines_main_and_repeated_done() -> None:
    """Test that global timerange combines main DONE task and repeated DONE tasks."""
    org_content = """
* DONE Task 1
CLOSED: [2024-01-10 Wed 10:00]

* TODO Task 2 with repeats
:LOGBOOK:
- State "DONE"       from "TODO"       [2024-01-15 Mon 11:00]
- State "DONE"       from "TODO"       [2024-01-20 Sat 12:00]
:END:

* DONE Task 3
CLOSED: [2024-01-25 Thu 14:00]
"""
    nodes = orgparse.loads(org_content)
    result = analyze(list(nodes[1:]), {}, "tags", 10)

    assert result.timerange.earliest == datetime(2024, 1, 10, 10, 0)
    assert result.timerange.latest == datetime(2024, 1, 25, 14, 0)
    assert len(result.timerange.timeline) == 4


def test_global_timerange_timeline_counts_same_day() -> None:
    """Test that timeline correctly counts multiple tasks on the same day."""
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

    from datetime import date

    assert result.timerange.timeline[date(2024, 1, 15)] == 3
    assert len(result.timerange.timeline) == 1


def test_global_timerange_with_scheduled_fallback() -> None:
    """Test that global timerange uses scheduled timestamp when closed is missing."""
    org_content = """
* DONE Task 1
SCHEDULED: <2024-01-15 Mon>
"""
    nodes = orgparse.loads(org_content)
    result = analyze(list(nodes[1:]), {}, "tags", 10)

    assert result.timerange.earliest is not None
    assert result.timerange.latest is not None


def test_global_timerange_ignores_tasks_without_timestamps() -> None:
    """Test that tasks without any timestamps don't affect the timerange."""
    org_content = """
* DONE Task 1
CLOSED: [2024-01-15 Mon 10:00]

* DONE Task 2

* DONE Task 3
CLOSED: [2024-01-20 Sat 14:00]
"""
    nodes = orgparse.loads(org_content)
    result = analyze(list(nodes[1:]), {}, "tags", 10)

    assert result.timerange.earliest == datetime(2024, 1, 15, 10, 0)
    assert result.timerange.latest == datetime(2024, 1, 20, 14, 0)
    assert len(result.timerange.timeline) == 2


def test_global_timerange_works_across_categories() -> None:
    """Test that global timerange is consistent across different categories."""
    org_content = """
* DONE Task 1 :tag1:
CLOSED: [2024-01-15 Mon 10:00]

* DONE Task 2 :tag2:
CLOSED: [2024-01-20 Sat 14:00]
"""
    nodes = orgparse.loads(org_content)

    result_tags = analyze(list(nodes[1:]), {}, "tags", 10)
    result_heading = analyze(list(nodes[1:]), {}, "heading", 10)
    result_body = analyze(list(nodes[1:]), {}, "body", 10)

    assert result_tags.timerange.earliest == result_heading.timerange.earliest
    assert result_tags.timerange.latest == result_body.timerange.latest
    assert result_tags.timerange.earliest == datetime(2024, 1, 15, 10, 0)
    assert result_tags.timerange.latest == datetime(2024, 1, 20, 14, 0)
