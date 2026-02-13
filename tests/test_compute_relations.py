"""Tests for the compute_relations() function."""

from orgstats.core import compute_relations
from tests.conftest import node_from_org


def test_compute_relations_empty_nodes() -> None:
    """Test with empty nodes list."""
    nodes = node_from_org("")

    relations = compute_relations(nodes, {}, "tags")

    assert relations == {}


def test_compute_relations_single_tag() -> None:
    """Test single tag creates no relations."""
    nodes = node_from_org("* DONE Task :Python:\n")

    relations = compute_relations(nodes, {}, "tags")

    assert relations == {}


def test_compute_relations_two_tags() -> None:
    """Test two tags create bidirectional relation."""
    nodes = node_from_org("* DONE Task :Python:Testing:\n")

    relations = compute_relations(nodes, {}, "tags")

    assert "python" in relations
    assert "testing" in relations
    assert relations["python"].relations["testing"] == 1
    assert relations["testing"].relations["python"] == 1


def test_compute_relations_three_tags() -> None:
    """Test three tags create all pair-wise relations."""
    nodes = node_from_org("* DONE Task :A:B:C:\n")

    relations = compute_relations(nodes, {}, "tags")

    assert len(relations) == 3
    assert relations["a"].relations["b"] == 1
    assert relations["a"].relations["c"] == 1
    assert relations["b"].relations["a"] == 1
    assert relations["b"].relations["c"] == 1
    assert relations["c"].relations["a"] == 1
    assert relations["c"].relations["b"] == 1


def test_compute_relations_accumulates() -> None:
    """Test multiple nodes accumulate relations."""
    nodes = node_from_org("""
* DONE Task :Python:Testing:
* DONE Task :Python:Testing:
""")

    relations = compute_relations(nodes, {}, "tags")

    assert relations["python"].relations["testing"] == 2
    assert relations["testing"].relations["python"] == 2


def test_compute_relations_repeated_tasks() -> None:
    """Test repeated tasks count correctly."""
    nodes = node_from_org("""
* TODO Task :Python:Testing:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
- State "DONE"       from "TODO"       [2023-10-19 Thu 09:10]
:END:
""")

    relations = compute_relations(nodes, {}, "tags")

    assert relations["python"].relations["testing"] == 2
    assert relations["testing"].relations["python"] == 2


def test_compute_relations_with_mapping() -> None:
    """Test that mapping is applied."""
    nodes = node_from_org("* DONE Task :Test:SysAdmin:\n")

    relations = compute_relations(nodes, {"test": "testing", "sysadmin": "devops"}, "tags")

    assert "testing" in relations
    assert "devops" in relations
    assert relations["testing"].relations["devops"] == 1
    assert relations["devops"].relations["testing"] == 1


def test_compute_relations_heading_category() -> None:
    """Test relations for heading words."""
    nodes = node_from_org("* DONE Implement feature\n")

    relations = compute_relations(nodes, {}, "heading")

    assert "implement" in relations
    assert "feature" in relations
    assert relations["implement"].relations["feature"] == 1
    assert relations["feature"].relations["implement"] == 1


def test_compute_relations_body_category() -> None:
    """Test relations for body words."""
    nodes = node_from_org("""
* DONE Task
Python code
""")

    relations = compute_relations(nodes, {}, "body")

    assert "python" in relations
    assert "code" in relations
    assert relations["python"].relations["code"] == 1
    assert relations["code"].relations["python"] == 1


def test_compute_relations_no_self_relations() -> None:
    """Test that tags don't create relations with themselves."""
    nodes = node_from_org("* DONE Task :Python:Testing:\n")

    relations = compute_relations(nodes, {}, "tags")

    assert "python" not in relations["python"].relations
    assert "testing" not in relations["testing"].relations


def test_compute_relations_todo_task() -> None:
    """Test TODO task has no relations (count=0)."""
    nodes = node_from_org("* TODO Task :Python:Testing:\n")

    relations = compute_relations(nodes, {}, "tags")

    assert relations == {}


def test_compute_relations_mixed_nodes() -> None:
    """Test nodes with different tag combinations."""
    nodes = node_from_org("""
* DONE Task :Python:Testing:
* DONE Task :Python:Debugging:
* DONE Task :Testing:Debugging:
""")

    relations = compute_relations(nodes, {}, "tags")

    assert relations["python"].relations["testing"] == 1
    assert relations["python"].relations["debugging"] == 1
    assert relations["testing"].relations["python"] == 1
    assert relations["testing"].relations["debugging"] == 1
    assert relations["debugging"].relations["python"] == 1
    assert relations["debugging"].relations["testing"] == 1
