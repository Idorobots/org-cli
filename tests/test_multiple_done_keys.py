"""Tests for multiple done_keys support across all functions."""

from datetime import datetime

from orgstats.analyze import (
    compute_day_of_week_histogram,
    compute_frequencies,
    compute_global_timerange,
    compute_relations,
    compute_task_stats,
    compute_time_ranges,
)
from orgstats.timestamp import extract_timestamp
from tests.conftest import node_from_org


def test_compute_done_count_with_multiple_done_keys() -> None:
    """Test that multiple done states are all treated as completed."""
    nodes = node_from_org(
        """
* DONE Task 1 :tag1:
* CANCELLED Task 2 :tag2:
* ARCHIVED Task 3 :tag3:
* TODO Task 4 :tag4:
""",
        todo_keys=["TODO"],
        done_keys=["DONE", "CANCELLED", "ARCHIVED"],
    )

    frequencies = compute_frequencies(nodes, {}, "tags", ["DONE", "CANCELLED", "ARCHIVED"])

    assert "tag1" in frequencies
    assert "tag2" in frequencies
    assert "tag3" in frequencies
    assert "tag4" not in frequencies
    assert frequencies["tag1"].total == 1
    assert frequencies["tag2"].total == 1
    assert frequencies["tag3"].total == 1


def test_extract_timestamp_with_multiple_done_keys() -> None:
    """Test extract_timestamp recognizes multiple done states in repeated tasks."""
    nodes = node_from_org("""
* TODO Task
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 14:43]
- State "CANCELLED"  from "TODO"       [2023-10-19 Thu 10:00]
- State "ARCHIVED"   from "TODO"       [2023-10-18 Wed 09:15]
- State "TODO"       from "DONE"       [2023-10-17 Tue 08:00]
:END:
""")

    timestamps = extract_timestamp(nodes[0], ["DONE", "CANCELLED", "ARCHIVED"])

    assert len(timestamps) == 3
    days = sorted([t.day for t in timestamps])
    assert days == [18, 19, 20]


def test_extract_timestamp_filters_by_done_keys() -> None:
    """Test that extract_timestamp only includes specified done states."""
    nodes = node_from_org("""
* TODO Task
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 14:43]
- State "CANCELLED"  from "TODO"       [2023-10-19 Thu 10:00]
- State "ARCHIVED"   from "TODO"       [2023-10-18 Wed 09:15]
:END:
""")

    timestamps_done_only = extract_timestamp(nodes[0], ["DONE"])
    assert len(timestamps_done_only) == 1
    assert timestamps_done_only[0].day == 20

    timestamps_cancelled_only = extract_timestamp(nodes[0], ["CANCELLED"])
    assert len(timestamps_cancelled_only) == 1
    assert timestamps_cancelled_only[0].day == 19

    timestamps_all = extract_timestamp(nodes[0], ["DONE", "CANCELLED", "ARCHIVED"])
    assert len(timestamps_all) == 3


def test_compute_task_stats_with_multiple_done_keys() -> None:
    """Test that max_repeat_count considers all done states."""
    nodes = node_from_org("""
* TODO Task
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
- State "CANCELLED"  from "TODO"       [2023-10-19 Thu 09:10]
- State "ARCHIVED"   from "TODO"       [2023-10-18 Wed 09:05]
:END:
""")

    total, max_repeat = compute_task_stats(nodes, ["DONE", "CANCELLED", "ARCHIVED"])

    assert total == 3
    assert max_repeat == 3


def test_compute_task_stats_only_counts_specified_done_keys() -> None:
    """Test that only specified done keys are counted."""
    nodes = node_from_org("""
* TODO Task
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
- State "CANCELLED"  from "TODO"       [2023-10-19 Thu 09:10]
- State "ARCHIVED"   from "TODO"       [2023-10-18 Wed 09:05]
:END:
""")

    total_done_only, max_repeat_done_only = compute_task_stats(nodes, ["DONE"])
    assert max_repeat_done_only == 1

    total_all, max_repeat_all = compute_task_stats(nodes, ["DONE", "CANCELLED", "ARCHIVED"])
    assert max_repeat_all == 3


def test_compute_day_of_week_histogram_with_multiple_done_keys() -> None:
    """Test that day of week histogram includes all done states."""
    nodes = node_from_org(
        """
* DONE Task 1
CLOSED: [2023-10-20 Fri 14:43]

* CANCELLED Task 2
CLOSED: [2023-10-21 Sat 10:00]

* ARCHIVED Task 3
CLOSED: [2023-10-22 Sun 15:30]
""",
        done_keys=["DONE", "CANCELLED", "ARCHIVED"],
    )

    histogram = compute_day_of_week_histogram(nodes, ["DONE", "CANCELLED", "ARCHIVED"])

    assert histogram.values["Friday"] == 1
    assert histogram.values["Saturday"] == 1
    assert histogram.values["Sunday"] == 1


def test_compute_global_timerange_with_multiple_done_keys() -> None:
    """Test that global timerange includes all done states."""
    nodes = node_from_org(
        """
* DONE Task 1
CLOSED: [2023-10-18 Wed 09:15]

* CANCELLED Task 2
CLOSED: [2023-10-20 Fri 14:43]

* ARCHIVED Task 3
CLOSED: [2023-10-22 Sun 16:00]
""",
        done_keys=["DONE", "CANCELLED", "ARCHIVED"],
    )

    timerange = compute_global_timerange(nodes, ["DONE", "CANCELLED", "ARCHIVED"])

    dt1 = datetime(2023, 10, 18, 9, 15)
    dt3 = datetime(2023, 10, 22, 16, 0)
    assert timerange.earliest == dt1
    assert timerange.latest == dt3


def test_compute_global_timerange_filters_by_done_keys() -> None:
    """Test that only specified done keys are included in timerange."""
    nodes = node_from_org(
        """
* DONE Task 1
CLOSED: [2023-10-18 Wed 09:15]

* CANCELLED Task 2
CLOSED: [2023-10-20 Fri 14:43]

* ARCHIVED Task 3
CLOSED: [2023-10-22 Sun 16:00]
""",
        done_keys=["DONE", "CANCELLED", "ARCHIVED"],
    )

    timerange_done_only = compute_global_timerange(nodes, ["DONE"])
    assert timerange_done_only.earliest == datetime(2023, 10, 18, 9, 15)
    assert timerange_done_only.latest == datetime(2023, 10, 18, 9, 15)

    timerange_all = compute_global_timerange(nodes, ["DONE", "CANCELLED", "ARCHIVED"])
    assert timerange_all.earliest == datetime(2023, 10, 18, 9, 15)
    assert timerange_all.latest == datetime(2023, 10, 22, 16, 0)


def test_compute_frequencies_with_multiple_done_keys() -> None:
    """Test that frequencies count all done states."""
    nodes = node_from_org(
        """
* DONE Task :python:
* CANCELLED Task :python:
* ARCHIVED Task :python:
* TODO Task :python:
""",
        todo_keys=["TODO"],
        done_keys=["DONE", "CANCELLED", "ARCHIVED"],
    )

    frequencies = compute_frequencies(nodes, {}, "tags", ["DONE", "CANCELLED", "ARCHIVED"])

    assert frequencies["python"].total == 3


def test_compute_frequencies_with_repeated_tasks_multiple_done_keys() -> None:
    """Test frequencies with repeated tasks and multiple done keys."""
    nodes = node_from_org("""
* TODO Task :daily:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
- State "CANCELLED"  from "TODO"       [2023-10-19 Thu 09:10]
:END:
""")

    frequencies = compute_frequencies(nodes, {}, "tags", ["DONE", "CANCELLED"])

    assert frequencies["daily"].total == 2


def test_compute_relations_with_multiple_done_keys() -> None:
    """Test that relations consider all done states."""
    nodes = node_from_org(
        """
* DONE Task :python:testing:
* CANCELLED Task :python:testing:
* ARCHIVED Task :python:testing:
* TODO Task :python:testing:
""",
        todo_keys=["TODO"],
        done_keys=["DONE", "CANCELLED", "ARCHIVED"],
    )

    relations = compute_relations(nodes, {}, "tags", ["DONE", "CANCELLED", "ARCHIVED"])

    assert "python" in relations
    assert "testing" in relations
    assert relations["python"].relations["testing"] == 3
    assert relations["testing"].relations["python"] == 3


def test_compute_time_ranges_with_multiple_done_keys() -> None:
    """Test that time ranges include all done states."""
    nodes = node_from_org(
        """
* DONE Task :python:
CLOSED: [2023-10-18 Wed 09:15]

* CANCELLED Task :python:
CLOSED: [2023-10-20 Fri 14:43]

* ARCHIVED Task :python:
CLOSED: [2023-10-22 Sun 16:00]

* TODO Task :python:
CLOSED: [2023-10-25 Wed 12:00]
""",
        todo_keys=["TODO"],
        done_keys=["DONE", "CANCELLED", "ARCHIVED"],
    )

    time_ranges = compute_time_ranges(nodes, {}, "tags", ["DONE", "CANCELLED", "ARCHIVED"])

    assert "python" in time_ranges
    tr = time_ranges["python"]
    assert tr.earliest == datetime(2023, 10, 18, 9, 15)
    assert tr.latest == datetime(2023, 10, 22, 16, 0)
    assert len(tr.timeline) == 3


def test_compute_time_ranges_excludes_non_done_keys() -> None:
    """Test that time ranges exclude tasks not in done_keys."""
    nodes = node_from_org("""
* DONE Task :python:
CLOSED: [2023-10-18 Wed 09:15]

* TODO Task :python:
CLOSED: [2023-10-25 Wed 12:00]
""")

    time_ranges = compute_time_ranges(nodes, {}, "tags", ["DONE"])

    assert "python" in time_ranges
    tr = time_ranges["python"]
    assert tr.earliest == datetime(2023, 10, 18, 9, 15)
    assert tr.latest == datetime(2023, 10, 18, 9, 15)
    assert len(tr.timeline) == 1


def test_multiple_done_keys_with_custom_states() -> None:
    """Test using custom completion states."""
    nodes = node_from_org(
        """
* COMPLETED Task 1 :tag1:
* FINISHED Task 2 :tag2:
* RESOLVED Task 3 :tag3:
* TODO Task 4 :tag4:
""",
        todo_keys=["TODO"],
        done_keys=["COMPLETED", "FINISHED", "RESOLVED"],
    )

    frequencies = compute_frequencies(nodes, {}, "tags", ["COMPLETED", "FINISHED", "RESOLVED"])

    assert "tag1" in frequencies
    assert "tag2" in frequencies
    assert "tag3" in frequencies
    assert "tag4" not in frequencies
    assert frequencies["tag1"].total == 1
    assert frequencies["tag2"].total == 1
    assert frequencies["tag3"].total == 1


def test_empty_done_keys_list() -> None:
    """Test that empty done_keys list results in no completed tasks."""
    nodes = node_from_org("""
* DONE Task 1 :tag1:
* CANCELLED Task 2 :tag2:
""")

    frequencies = compute_frequencies(nodes, {}, "tags", [])

    assert frequencies == {}


def test_single_done_key() -> None:
    """Test backward compatibility with single done key."""
    nodes = node_from_org("""
* DONE Task 1 :tag1:
* CANCELLED Task 2 :tag2:
""")

    frequencies = compute_frequencies(nodes, {}, "tags", ["DONE"])

    assert "tag1" in frequencies
    assert "tag2" not in frequencies
    assert frequencies["tag1"].total == 1


def test_case_sensitive_done_keys() -> None:
    """Test that done_keys matching is case-sensitive."""
    nodes = node_from_org(
        """
* DONE Task 1 :tag1:
* done Task 2 :tag2:
""",
        done_keys=["DONE", "done"],
    )

    frequencies_upper = compute_frequencies(nodes, {}, "tags", ["DONE"])
    assert "tag1" in frequencies_upper
    assert "tag2" not in frequencies_upper

    frequencies_lower = compute_frequencies(nodes, {}, "tags", ["done"])
    assert "tag1" not in frequencies_lower
    assert "tag2" in frequencies_lower
