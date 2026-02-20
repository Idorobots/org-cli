"""Tests for the compute_time_ranges() function."""

from datetime import date, datetime

from orgstats.analyze import compute_time_ranges
from tests.conftest import node_from_org


def test_compute_time_ranges_empty_nodes() -> None:
    """Test with empty nodes list."""
    nodes = node_from_org("")

    time_ranges = compute_time_ranges(nodes, {}, "tags")

    assert time_ranges == {}


def test_compute_time_ranges_node_without_timestamps() -> None:
    """Test with node that has no timestamps."""
    nodes = node_from_org("* DONE Task :Python:\n")

    time_ranges = compute_time_ranges(nodes, {}, "tags")

    assert time_ranges == {}


def test_compute_time_ranges_single_tag_single_timestamp() -> None:
    """Test single tag with single timestamp."""
    nodes = node_from_org("""
* DONE Task :Python:
CLOSED: [2023-10-20 Fri 14:43]
""")

    time_ranges = compute_time_ranges(nodes, {}, "tags")

    assert "Python" in time_ranges
    dt = datetime(2023, 10, 20, 14, 43)
    assert time_ranges["Python"].earliest == dt
    assert time_ranges["Python"].latest == dt


def test_compute_time_ranges_single_tag_multiple_timestamps() -> None:
    """Test single tag with multiple timestamps via repeated tasks."""
    nodes = node_from_org("""
* TODO Task :Python:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 14:43]
- State "DONE"       from "TODO"       [2023-10-19 Thu 10:00]
- State "DONE"       from "TODO"       [2023-10-18 Wed 09:15]
:END:
""")

    time_ranges = compute_time_ranges(nodes, {}, "tags")

    assert "Python" in time_ranges
    dt1 = datetime(2023, 10, 18, 9, 15)
    dt3 = datetime(2023, 10, 20, 14, 43)
    assert time_ranges["Python"].earliest == dt1
    assert time_ranges["Python"].latest == dt3


def test_compute_time_ranges_multiple_tags() -> None:
    """Test multiple tags with same timestamps."""
    nodes = node_from_org("""
* DONE Task :Python:Testing:Debugging:
CLOSED: [2023-10-20 Fri 14:43]
""")

    time_ranges = compute_time_ranges(nodes, {}, "tags")

    assert len(time_ranges) == 3
    dt = datetime(2023, 10, 20, 14, 43)
    assert time_ranges["Python"].earliest == dt
    assert time_ranges["Python"].latest == dt
    assert time_ranges["Testing"].earliest == dt
    assert time_ranges["Testing"].latest == dt
    assert time_ranges["Debugging"].earliest == dt
    assert time_ranges["Debugging"].latest == dt


def test_compute_time_ranges_accumulates() -> None:
    """Test multiple nodes accumulate correctly."""
    nodes = node_from_org("""
* DONE Task :Python:
CLOSED: [2023-10-18 Wed 09:15]

* DONE Task :Python:Testing:
CLOSED: [2023-10-20 Fri 14:43]
""")

    time_ranges = compute_time_ranges(nodes, {}, "tags")

    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 20, 14, 43)
    assert time_ranges["Python"].earliest == dt1
    assert time_ranges["Python"].latest == dt2
    assert time_ranges["Testing"].earliest == dt2
    assert time_ranges["Testing"].latest == dt2


def test_compute_time_ranges_with_mapping() -> None:
    """Test that mapping is applied."""
    nodes = node_from_org("""
* DONE Task :Test:SysAdmin:
CLOSED: [2023-10-20 Fri 14:43]
""")

    time_ranges = compute_time_ranges(nodes, {"Test": "Testing", "SysAdmin": "DevOps"}, "tags")

    assert "Testing" in time_ranges
    assert "DevOps" in time_ranges
    assert "test" not in time_ranges
    assert "sysadmin" not in time_ranges


def test_compute_time_ranges_timeline_single_timestamp() -> None:
    """Test single timestamp creates timeline entry."""
    nodes = node_from_org("""
* DONE Task :Python:
CLOSED: [2023-10-20 Fri 14:43]
""")

    time_ranges = compute_time_ranges(nodes, {}, "tags")

    timeline = time_ranges["Python"].timeline
    assert len(timeline) == 1
    assert timeline[date(2023, 10, 20)] == 1


def test_compute_time_ranges_timeline_multiple_timestamps() -> None:
    """Test multiple timestamps on different days create multiple timeline entries."""
    nodes = node_from_org("""
* TODO Task :Python:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 14:43]
- State "DONE"       from "TODO"       [2023-10-19 Thu 10:00]
- State "DONE"       from "TODO"       [2023-10-18 Wed 09:15]
:END:
""")

    time_ranges = compute_time_ranges(nodes, {}, "tags")

    timeline = time_ranges["Python"].timeline
    assert len(timeline) == 3
    assert timeline[date(2023, 10, 18)] == 1
    assert timeline[date(2023, 10, 19)] == 1
    assert timeline[date(2023, 10, 20)] == 1


def test_compute_time_ranges_timeline_same_day_timestamps() -> None:
    """Test multiple timestamps on same day increment counter."""
    nodes = node_from_org("""
* TODO Task :Python:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 14:43]
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
:END:
""")

    time_ranges = compute_time_ranges(nodes, {}, "tags")

    timeline = time_ranges["Python"].timeline
    assert len(timeline) == 1
    assert timeline[date(2023, 10, 20)] == 2


def test_compute_time_ranges_timeline_accumulates() -> None:
    """Test multiple nodes accumulate timeline correctly."""
    nodes = node_from_org("""
* DONE Task :Python:
CLOSED: [2023-10-18 Wed 09:15]

* DONE Task :Python:
CLOSED: [2023-10-18 Wed 14:30]

* DONE Task :Python:
CLOSED: [2023-10-19 Thu 10:00]
""")

    time_ranges = compute_time_ranges(nodes, {}, "tags")

    timeline = time_ranges["Python"].timeline
    assert len(timeline) == 2
    assert timeline[date(2023, 10, 18)] == 2
    assert timeline[date(2023, 10, 19)] == 1


def test_compute_time_ranges_timeline_multiple_tags() -> None:
    """Test multiple tags all get timeline entries."""
    nodes = node_from_org("""
* TODO Task :Python:Testing:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-19 Thu 10:00]
- State "DONE"       from "TODO"       [2023-10-18 Wed 09:15]
:END:
""")

    time_ranges = compute_time_ranges(nodes, {}, "tags")

    python_timeline = time_ranges["Python"].timeline
    testing_timeline = time_ranges["Testing"].timeline

    assert len(python_timeline) == 2
    assert python_timeline[date(2023, 10, 18)] == 1
    assert python_timeline[date(2023, 10, 19)] == 1

    assert len(testing_timeline) == 2
    assert testing_timeline[date(2023, 10, 18)] == 1
    assert testing_timeline[date(2023, 10, 19)] == 1


def test_compute_time_ranges_heading_category() -> None:
    """Test time ranges for heading words."""
    nodes = node_from_org("""
* DONE Implement feature
CLOSED: [2023-10-20 Fri 14:43]
""")

    time_ranges = compute_time_ranges(nodes, {}, "heading")

    assert "implement" in time_ranges
    assert "feature" in time_ranges


def test_compute_time_ranges_body_category() -> None:
    """Test time ranges for body words."""
    nodes = node_from_org("""
* DONE Task
CLOSED: [2023-10-20 Fri 14:43]
Python code
""")

    time_ranges = compute_time_ranges(nodes, {}, "body")

    assert "python" in time_ranges
    assert "code" in time_ranges
