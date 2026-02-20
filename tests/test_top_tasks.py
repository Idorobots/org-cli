"""Tests for top tasks display functionality."""

from datetime import datetime

from orgstats.cli import get_most_recent_timestamp, get_top_tasks
from tests.conftest import node_from_org


def test_get_most_recent_timestamp_with_closed() -> None:
    """Test get_most_recent_timestamp with closed timestamp."""
    org_text = """* DONE Task
CLOSED: [2023-10-15 Sun 14:00]
"""
    nodes = node_from_org(org_text)

    timestamp = get_most_recent_timestamp(nodes[0])

    assert timestamp == datetime(2023, 10, 15, 14, 0)


def test_get_most_recent_timestamp_with_repeats() -> None:
    """Test get_most_recent_timestamp with repeated tasks."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2023-10-10 Tue 09:00]
- State "DONE" from "TODO" [2023-10-15 Sun 14:00]
- State "DONE" from "TODO" [2023-10-12 Thu 11:00]
:END:
"""
    nodes = node_from_org(org_text)

    timestamp = get_most_recent_timestamp(nodes[0])

    assert timestamp == datetime(2023, 10, 15, 14, 0)


def test_get_most_recent_timestamp_with_scheduled() -> None:
    """Test get_most_recent_timestamp with scheduled timestamp."""
    org_text = """* TODO Task
SCHEDULED: <2023-10-20 Fri 10:00>
"""
    nodes = node_from_org(org_text)

    timestamp = get_most_recent_timestamp(nodes[0])

    assert timestamp == datetime(2023, 10, 20, 10, 0)


def test_get_most_recent_timestamp_no_timestamp() -> None:
    """Test get_most_recent_timestamp with no timestamp."""
    org_text = """* TODO Task
"""
    nodes = node_from_org(org_text)

    timestamp = get_most_recent_timestamp(nodes[0])

    assert timestamp is None


def test_get_top_tasks_sorted_by_timestamp() -> None:
    """Test get_top_tasks returns nodes sorted by most recent timestamp."""
    org_text = """* DONE Task 1
CLOSED: [2023-10-15 Sun 14:00]

* DONE Task 2
CLOSED: [2023-10-20 Fri 10:00]

* DONE Task 3
CLOSED: [2023-10-10 Tue 09:00]
"""
    nodes = node_from_org(org_text)

    top_tasks = get_top_tasks(nodes, 3)

    assert len(top_tasks) == 3
    assert top_tasks[0].heading == "Task 2"
    assert top_tasks[1].heading == "Task 1"
    assert top_tasks[2].heading == "Task 3"


def test_get_top_tasks_respects_max_results() -> None:
    """Test get_top_tasks respects max_results limit."""
    org_text = """* DONE Task 1
CLOSED: [2023-10-15 Sun 14:00]

* DONE Task 2
CLOSED: [2023-10-20 Fri 10:00]

* DONE Task 3
CLOSED: [2023-10-10 Tue 09:00]
"""
    nodes = node_from_org(org_text)

    top_tasks = get_top_tasks(nodes, 2)

    assert len(top_tasks) == 2
    assert top_tasks[0].heading == "Task 2"
    assert top_tasks[1].heading == "Task 1"


def test_get_top_tasks_filters_nodes_without_timestamps() -> None:
    """Test get_top_tasks filters out nodes without timestamps."""
    org_text = """* DONE Task 1
CLOSED: [2023-10-15 Sun 14:00]

* TODO Task 2

* DONE Task 3
CLOSED: [2023-10-10 Tue 09:00]
"""
    nodes = node_from_org(org_text)

    top_tasks = get_top_tasks(nodes, 3)

    assert len(top_tasks) == 2
    assert top_tasks[0].heading == "Task 1"
    assert top_tasks[1].heading == "Task 3"


def test_get_top_tasks_empty_list() -> None:
    """Test get_top_tasks with empty list."""
    top_tasks = get_top_tasks([], 10)

    assert top_tasks == []


def test_get_top_tasks_all_nodes_without_timestamps() -> None:
    """Test get_top_tasks when all nodes have no timestamps."""
    org_text = """* TODO Task 1

* TODO Task 2
"""
    nodes = node_from_org(org_text)

    top_tasks = get_top_tasks(nodes, 10)

    assert top_tasks == []
