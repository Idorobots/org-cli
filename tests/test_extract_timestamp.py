"""Tests for the extract_timestamp() function."""

from datetime import datetime

from orgstats.core import extract_timestamp
from tests.conftest import node_from_org


def test_extract_timestamp_empty_node() -> None:
    """Test node with no timestamps returns empty list."""
    nodes = node_from_org("* TODO Task\n")
    timestamps = extract_timestamp(nodes[0])
    assert timestamps == []


def test_extract_timestamp_repeated_tasks_priority() -> None:
    """Test repeated DONE tasks take priority."""
    nodes = node_from_org("""
* DONE Task
CLOSED: [2023-10-25 Wed 10:00]
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 14:43]
:END:
""")

    timestamps = extract_timestamp(nodes[0])

    assert len(timestamps) == 1
    assert timestamps[0].day == 20


def test_extract_timestamp_repeated_tasks_all_done() -> None:
    """Test all DONE repeated tasks are returned."""
    nodes = node_from_org("""
* TODO Task
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 14:43]
- State "DONE"       from "TODO"       [2023-10-19 Thu 10:00]
- State "DONE"       from "TODO"       [2023-10-18 Wed 09:15]
:END:
""")

    timestamps = extract_timestamp(nodes[0])

    assert len(timestamps) == 3
    days = sorted([t.day for t in timestamps])
    assert days == [18, 19, 20]


def test_extract_timestamp_repeated_tasks_mixed() -> None:
    """Test only DONE repeated tasks returned (not TODO)."""
    nodes = node_from_org("""
* TODO Task
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 14:43]
- State "TODO"       from "DONE"       [2023-10-19 Thu 10:00]
- State "DONE"       from "TODO"       [2023-10-18 Wed 09:15]
:END:
""")

    timestamps = extract_timestamp(nodes[0])

    assert len(timestamps) == 2
    days = sorted([t.day for t in timestamps])
    assert days == [18, 20]


def test_extract_timestamp_repeated_tasks_empty() -> None:
    """Test falls back to closed when no DONE repeats."""
    nodes = node_from_org("""
* DONE Task
CLOSED: [2023-10-25 Wed 10:00]
:LOGBOOK:
- State "TODO"       from "DONE"       [2023-10-20 Fri 14:43]
:END:
""")

    timestamps = extract_timestamp(nodes[0])

    assert len(timestamps) == 1
    assert timestamps[0].day == 25


def test_extract_timestamp_closed_fallback() -> None:
    """Test closed timestamp used when no repeated tasks."""
    nodes = node_from_org("""
* DONE Task
CLOSED: [2023-10-20 Fri 14:43]
""")

    timestamps = extract_timestamp(nodes[0])

    assert len(timestamps) == 1
    assert timestamps[0].day == 20 and timestamps[0].hour == 14 and timestamps[0].minute == 43


def test_extract_timestamp_scheduled_fallback() -> None:
    """Test scheduled used when no closed timestamp."""
    nodes = node_from_org("""
* TODO Task
SCHEDULED: <2023-10-20 Fri>
""")

    timestamps = extract_timestamp(nodes[0])

    assert len(timestamps) == 1
    assert timestamps[0].day == 20


def test_extract_timestamp_deadline_fallback() -> None:
    """Test deadline used when no scheduled timestamp."""
    nodes = node_from_org("""
* TODO Task
DEADLINE: <2023-10-25 Wed>
""")

    timestamps = extract_timestamp(nodes[0])

    assert len(timestamps) == 1
    assert timestamps[0].day == 25


def test_extract_timestamp_priority_order() -> None:
    """Test that priority order is respected."""
    nodes = node_from_org("""
* DONE Task
CLOSED: [2023-10-21 Sat 10:00]
SCHEDULED: <2023-10-22 Sun>
DEADLINE: <2023-10-25 Wed>
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 14:43]
:END:
""")

    timestamps = extract_timestamp(nodes[0])

    assert len(timestamps) == 1
    assert timestamps[0].day == 20


def test_extract_timestamp_closed_none() -> None:
    """Test handles closed=None gracefully."""
    nodes = node_from_org("""
* TODO Task
SCHEDULED: <2023-10-20 Fri>
""")

    timestamps = extract_timestamp(nodes[0])

    assert len(timestamps) == 1
    assert timestamps[0].day == 20


def test_extract_timestamp_scheduled_none() -> None:
    """Test handles scheduled=None gracefully."""
    nodes = node_from_org("""
* TODO Task
DEADLINE: <2023-10-25 Wed>
""")

    timestamps = extract_timestamp(nodes[0])

    assert len(timestamps) == 1
    assert timestamps[0].day == 25


def test_extract_timestamp_deadline_none() -> None:
    """Test handles deadline=None gracefully."""
    nodes = node_from_org("* TODO Task\n")

    timestamps = extract_timestamp(nodes[0])

    assert timestamps == []


def test_extract_timestamp_returns_datetime_objects() -> None:
    """Test return type is datetime.datetime."""
    nodes = node_from_org("""
* DONE Task
CLOSED: [2023-10-20 Fri 14:43]
""")

    timestamps = extract_timestamp(nodes[0])

    assert len(timestamps) == 1
    assert isinstance(timestamps[0], datetime)


def test_extract_timestamp_date_only() -> None:
    """Test extraction with date-only timestamps."""
    nodes = node_from_org("""
* TODO Task
SCHEDULED: <2023-10-20 Fri>
""")

    timestamps = extract_timestamp(nodes[0])

    assert len(timestamps) == 1
    assert timestamps[0].day == 20


def test_extract_timestamp_single_done_in_repeats() -> None:
    """Test single DONE task in repeated tasks."""
    nodes = node_from_org("""
* TODO Task
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 14:43]
:END:
""")

    timestamps = extract_timestamp(nodes[0])

    assert len(timestamps) == 1
    assert timestamps[0].day == 20 and timestamps[0].hour == 14 and timestamps[0].minute == 43
