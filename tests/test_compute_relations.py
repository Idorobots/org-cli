"""Tests for the compute_relations() function."""

from orgstats.analyze import compute_relations
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

    assert "Python" in relations
    assert "Testing" in relations
    assert relations["Python"].relations["Testing"] == 1
    assert relations["Testing"].relations["Python"] == 1


def test_compute_relations_three_tags() -> None:
    """Test three tags create all pair-wise relations."""
    nodes = node_from_org("* DONE Task :A:B:C:\n")

    relations = compute_relations(nodes, {}, "tags")

    assert len(relations) == 3
    assert relations["A"].relations["B"] == 1
    assert relations["A"].relations["C"] == 1
    assert relations["B"].relations["A"] == 1
    assert relations["B"].relations["C"] == 1
    assert relations["C"].relations["A"] == 1
    assert relations["C"].relations["B"] == 1


def test_compute_relations_accumulates() -> None:
    """Test multiple nodes accumulate relations."""
    nodes = node_from_org("""
* DONE Task :Python:Testing:
* DONE Task :Python:Testing:
""")

    relations = compute_relations(nodes, {}, "tags")

    assert relations["Python"].relations["Testing"] == 2
    assert relations["Testing"].relations["Python"] == 2


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

    assert relations["Python"].relations["Testing"] == 2
    assert relations["Testing"].relations["Python"] == 2


def test_compute_relations_with_mapping() -> None:
    """Test that mapping is applied."""
    nodes = node_from_org("* DONE Task :Test:SysAdmin:\n")

    relations = compute_relations(nodes, {"Test": "Testing", "SysAdmin": "DevOps"}, "tags")

    assert "Testing" in relations
    assert "DevOps" in relations
    assert relations["Testing"].relations["DevOps"] == 1
    assert relations["DevOps"].relations["Testing"] == 1


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

    assert "Python" not in relations["Python"].relations
    assert "Testing" not in relations["Testing"].relations


def test_compute_relations_todo_task() -> None:
    """Test TODO task creates relations."""
    nodes = node_from_org("* TODO Task :Python:Testing:\n")

    relations = compute_relations(nodes, {}, "tags")

    assert relations["Python"].relations["Testing"] == 1
    assert relations["Testing"].relations["Python"] == 1


def test_compute_relations_mixed_nodes() -> None:
    """Test nodes with different tag combinations."""
    nodes = node_from_org("""
* DONE Task :Python:Testing:
* DONE Task :Python:Debugging:
* DONE Task :Testing:Debugging:
""")

    relations = compute_relations(nodes, {}, "tags")

    assert relations["Python"].relations["Testing"] == 1
    assert relations["Python"].relations["Debugging"] == 1
    assert relations["Testing"].relations["Python"] == 1
    assert relations["Testing"].relations["Debugging"] == 1
    assert relations["Debugging"].relations["Python"] == 1
    assert relations["Debugging"].relations["Testing"] == 1
