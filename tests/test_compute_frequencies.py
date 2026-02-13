"""Tests for the compute_frequencies() function."""

from orgstats.core import compute_frequencies
from tests.conftest import node_from_org


def test_compute_frequencies_empty_nodes() -> None:
    """Test with empty nodes list creates no entries."""
    nodes = node_from_org("")

    frequencies = compute_frequencies(nodes, {}, "tags")

    assert frequencies == {}


def test_compute_frequencies_single_tag() -> None:
    """Test single tag creates Frequency with correct count."""
    nodes = node_from_org("* DONE Task :Python:\n")

    frequencies = compute_frequencies(nodes, {}, "tags")

    assert "python" in frequencies
    assert frequencies["python"].total == 1


def test_compute_frequencies_multiple_tags() -> None:
    """Test multiple tags all get counted."""
    nodes = node_from_org("* DONE Task :Python:Testing:Debugging:\n")

    frequencies = compute_frequencies(nodes, {}, "tags")

    assert len(frequencies) == 3
    assert "python" in frequencies
    assert "testing" in frequencies
    assert "debugging" in frequencies
    assert frequencies["python"].total == 1
    assert frequencies["testing"].total == 1
    assert frequencies["debugging"].total == 1


def test_compute_frequencies_todo_task() -> None:
    """Test TODO task has count of 0."""
    nodes = node_from_org("* TODO Task :Python:\n")

    frequencies = compute_frequencies(nodes, {}, "tags")

    assert frequencies == {}


def test_compute_frequencies_repeated_tasks() -> None:
    """Test repeated tasks count correctly."""
    nodes = node_from_org("""
* TODO Task :Python:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
- State "DONE"       from "TODO"       [2023-10-19 Thu 09:10]
- State "DONE"       from "TODO"       [2023-10-18 Wed 09:05]
:END:
""")

    frequencies = compute_frequencies(nodes, {}, "tags")

    assert frequencies["python"].total == 3


def test_compute_frequencies_accumulates() -> None:
    """Test multiple nodes accumulate correctly."""
    nodes = node_from_org("""
* DONE Task :Python:
* DONE Task :Python:Testing:
""")

    frequencies = compute_frequencies(nodes, {}, "tags")

    assert frequencies["python"].total == 2
    assert frequencies["testing"].total == 1


def test_compute_frequencies_with_mapping() -> None:
    """Test that mapping is applied."""
    nodes = node_from_org("* DONE Task :Test:SysAdmin:\n")

    frequencies = compute_frequencies(nodes, {"test": "testing", "sysadmin": "devops"}, "tags")

    assert "testing" in frequencies
    assert "devops" in frequencies
    assert "test" not in frequencies
    assert "sysadmin" not in frequencies


def test_compute_frequencies_heading_category() -> None:
    """Test frequency computation for heading words."""
    nodes = node_from_org("""
* DONE Implement feature
* DONE Implement tests
""")

    frequencies = compute_frequencies(nodes, {}, "heading")

    assert frequencies["implement"].total == 2
    assert frequencies["feature"].total == 1
    assert frequencies["tests"].total == 1


def test_compute_frequencies_body_category() -> None:
    """Test frequency computation for body words."""
    nodes = node_from_org("""
* DONE Task
Python code
* DONE Task
Python tests
""")

    frequencies = compute_frequencies(nodes, {}, "body")

    assert frequencies["python"].total == 2
    assert frequencies["code"].total == 1
    assert frequencies["tests"].total == 1
