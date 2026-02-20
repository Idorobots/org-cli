"""Tests for the compute_day_of_week_histogram() function."""

from orgstats.analyze import compute_day_of_week_histogram
from tests.conftest import node_from_org


def test_compute_day_of_week_histogram_empty_nodes() -> None:
    """Test with empty nodes list."""
    nodes = node_from_org("")

    histogram = compute_day_of_week_histogram(nodes)

    assert histogram.values == {}


def test_compute_day_of_week_histogram_done_task_with_timestamp() -> None:
    """Test DONE task with closed timestamp."""
    nodes = node_from_org("""
* DONE Task
CLOSED: [2023-10-20 Fri 14:43]
""")

    histogram = compute_day_of_week_histogram(nodes)

    assert histogram.values["Friday"] == 1


def test_compute_day_of_week_histogram_done_task_no_timestamp() -> None:
    """Test DONE task without timestamp counts as unknown."""
    nodes = node_from_org("* DONE Task\n")

    histogram = compute_day_of_week_histogram(nodes)

    assert histogram.values["unknown"] == 1


def test_compute_day_of_week_histogram_todo_task_counted() -> None:
    """Test TODO task is counted."""
    nodes = node_from_org("""
* TODO Task
SCHEDULED: <2023-10-20 Fri>
""")

    histogram = compute_day_of_week_histogram(nodes)

    assert histogram.values["Friday"] == 1


def test_compute_day_of_week_histogram_repeated_tasks() -> None:
    """Test repeated tasks count each completion."""
    nodes = node_from_org("""
* TODO Task
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
- State "DONE"       from "TODO"       [2023-10-19 Thu 09:10]
- State "DONE"       from "TODO"       [2023-10-18 Wed 09:05]
:END:
""")

    histogram = compute_day_of_week_histogram(nodes)

    assert histogram.values["Friday"] == 1
    assert histogram.values["Thursday"] == 1
    assert histogram.values["Wednesday"] == 1


def test_compute_day_of_week_histogram_multiple_tasks() -> None:
    """Test multiple tasks on same day accumulate."""
    nodes = node_from_org("""
* DONE Task 1
CLOSED: [2023-10-20 Fri 09:15]

* DONE Task 2
CLOSED: [2023-10-20 Fri 14:43]
""")

    histogram = compute_day_of_week_histogram(nodes)

    assert histogram.values["Friday"] == 2


def test_compute_day_of_week_histogram_all_weekdays() -> None:
    """Test all days of the week."""
    nodes = node_from_org("""
* DONE Monday task
CLOSED: [2023-10-16 Mon 09:00]

* DONE Tuesday task
CLOSED: [2023-10-17 Tue 09:00]

* DONE Wednesday task
CLOSED: [2023-10-18 Wed 09:00]

* DONE Thursday task
CLOSED: [2023-10-19 Thu 09:00]

* DONE Friday task
CLOSED: [2023-10-20 Fri 09:00]

* DONE Saturday task
CLOSED: [2023-10-21 Sat 09:00]

* DONE Sunday task
CLOSED: [2023-10-22 Sun 09:00]
""")

    histogram = compute_day_of_week_histogram(nodes)

    assert histogram.values["Monday"] == 1
    assert histogram.values["Tuesday"] == 1
    assert histogram.values["Wednesday"] == 1
    assert histogram.values["Thursday"] == 1
    assert histogram.values["Friday"] == 1
    assert histogram.values["Saturday"] == 1
    assert histogram.values["Sunday"] == 1
