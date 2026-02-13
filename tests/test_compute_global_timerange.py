"""Tests for the compute_global_timerange() function."""

from datetime import datetime

from orgstats.core import compute_global_timerange
from tests.conftest import node_from_org


def test_compute_global_timerange_empty_nodes() -> None:
    """Test with empty nodes list."""
    nodes = node_from_org("")

    timerange = compute_global_timerange(nodes)

    assert timerange.earliest is None
    assert timerange.latest is None
    assert timerange.timeline == {}


def test_compute_global_timerange_single_done_task() -> None:
    """Test single DONE task."""
    nodes = node_from_org("""
* DONE Task
CLOSED: [2023-10-20 Fri 14:43]
""")

    timerange = compute_global_timerange(nodes)

    dt = datetime(2023, 10, 20, 14, 43)
    assert timerange.earliest == dt
    assert timerange.latest == dt


def test_compute_global_timerange_multiple_done_tasks() -> None:
    """Test multiple DONE tasks span timerange."""
    nodes = node_from_org("""
* DONE Task 1
CLOSED: [2023-10-18 Wed 09:15]

* DONE Task 2
CLOSED: [2023-10-20 Fri 14:43]
""")

    timerange = compute_global_timerange(nodes)

    dt1 = datetime(2023, 10, 18, 9, 15)
    dt2 = datetime(2023, 10, 20, 14, 43)
    assert timerange.earliest == dt1
    assert timerange.latest == dt2


def test_compute_global_timerange_todo_task_ignored() -> None:
    """Test TODO task is not included."""
    nodes = node_from_org("""
* TODO Task
SCHEDULED: <2023-10-20 Fri>
""")

    timerange = compute_global_timerange(nodes)

    assert timerange.earliest is None
    assert timerange.latest is None


def test_compute_global_timerange_repeated_tasks() -> None:
    """Test repeated tasks all included."""
    nodes = node_from_org("""
* TODO Task
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
- State "DONE"       from "TODO"       [2023-10-19 Thu 09:10]
- State "DONE"       from "TODO"       [2023-10-18 Wed 09:05]
:END:
""")

    timerange = compute_global_timerange(nodes)

    dt1 = datetime(2023, 10, 18, 9, 5)
    dt3 = datetime(2023, 10, 20, 9, 15)
    assert timerange.earliest == dt1
    assert timerange.latest == dt3


def test_compute_global_timerange_timeline() -> None:
    """Test timeline is built correctly."""
    nodes = node_from_org("""
* DONE Task 1
CLOSED: [2023-10-18 Wed 09:15]

* DONE Task 2
CLOSED: [2023-10-18 Wed 14:30]

* DONE Task 3
CLOSED: [2023-10-20 Fri 14:43]
""")

    timerange = compute_global_timerange(nodes)

    from datetime import date

    assert len(timerange.timeline) == 2
    assert timerange.timeline[date(2023, 10, 18)] == 2
    assert timerange.timeline[date(2023, 10, 20)] == 1


def test_compute_global_timerange_no_timestamps() -> None:
    """Test DONE task without timestamp is not included."""
    nodes = node_from_org("* DONE Task\n")

    timerange = compute_global_timerange(nodes)

    assert timerange.earliest is None
    assert timerange.latest is None
