"""Tests for relations computation in the analyze() function."""

import orgparse

from orgstats.analyze import analyze
from tests.conftest import node_from_org


def test_analyze_empty_nodes_has_empty_relations() -> None:
    """Test analyze with empty nodes returns empty relations."""
    nodes: list[orgparse.node.OrgNode] = []
    result = analyze(nodes, {}, category="tags", max_relations=3)

    assert result.tags == {}


def test_analyze_single_tag_no_relations() -> None:
    """Test task with single tag creates no Relations objects."""
    nodes = node_from_org("* DONE Task :Python:\n")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    assert result.tags["Python"].relations == {}


def test_analyze_two_tags_bidirectional_relation() -> None:
    """Test task with two tags creates bidirectional relation."""
    nodes = node_from_org("* DONE Task :Python:Testing:\n")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    assert "Python" in result.tags
    assert "Testing" in result.tags

    assert result.tags["Python"].relations["Testing"] == 1
    assert result.tags["Testing"].relations["Python"] == 1


def test_analyze_three_tags_all_relations() -> None:
    """Test task with three tags creates all bidirectional relations."""
    nodes = node_from_org("* DONE Task :TagA:TagB:TagC:\n")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    assert "TagA" in result.tags
    assert "TagB" in result.tags
    assert "TagC" in result.tags

    assert result.tags["TagA"].relations["TagB"] == 1
    assert result.tags["TagB"].relations["TagA"] == 1
    assert result.tags["TagA"].relations["TagC"] == 1
    assert result.tags["TagC"].relations["TagA"] == 1
    assert result.tags["TagB"].relations["TagC"] == 1
    assert result.tags["TagC"].relations["TagB"] == 1

    assert len(result.tags["TagA"].relations) == 2
    assert len(result.tags["TagB"].relations) == 2
    assert len(result.tags["TagC"].relations) == 2


def test_analyze_no_self_relations() -> None:
    """Test that tags do not create relations with themselves."""
    nodes = node_from_org("* DONE Task :Python:Testing:\n")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    assert "Python" not in result.tags["Python"].relations
    assert "Testing" not in result.tags["Testing"].relations


def test_analyze_relations_normalized() -> None:
    """Test that tag mapping applies to relations without normalization."""
    nodes = node_from_org("* DONE Task :Test:SysAdmin:\n")

    result = analyze(
        nodes,
        {"Test": "Testing", "SysAdmin": "DevOps"},
        category="tags",
        max_relations=3,
    )

    # "Test" -> "Testing" (mapped, no normalization)
    # "SysAdmin" -> "DevOps" (mapped, no normalization)
    assert "Testing" in result.tags
    assert "DevOps" in result.tags
    assert result.tags["Testing"].relations["DevOps"] == 1
    assert result.tags["DevOps"].relations["Testing"] == 1


def test_analyze_relations_accumulate() -> None:
    """Test that relations accumulate across multiple nodes."""
    nodes = node_from_org("""
* DONE Task :Python:Testing:
* DONE Task :Python:Testing:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    assert result.tags["Python"].relations["Testing"] == 2
    assert result.tags["Testing"].relations["Python"] == 2


def test_analyze_relations_with_repeated_tasks() -> None:
    """Test that repeated tasks increment relations by count."""
    nodes = node_from_org("""
* TODO Task :Daily:Meeting:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
- State "DONE"       from "TODO"       [2023-10-19 Thu 09:10]
:END:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    # count = max(0, 2) = 2
    assert result.tags["Daily"].relations["Meeting"] == 2
    assert result.tags["Meeting"].relations["Daily"] == 2


def test_analyze_heading_relations() -> None:
    """Test that heading word relations are computed for heading category."""
    nodes = node_from_org("* DONE Implement feature\n")

    result = analyze(nodes, {}, category="heading", max_relations=3)

    assert "implement" in result.tags
    assert "feature" in result.tags
    assert result.tags["implement"].relations["feature"] == 1
    assert result.tags["feature"].relations["implement"] == 1


def test_analyze_body_relations() -> None:
    """Test that body word relations are computed for body category."""
    nodes = node_from_org("* DONE Task\nPython code implementation\n")

    result = analyze(nodes, {}, category="body", max_relations=3)

    assert "python" in result.tags
    assert "code" in result.tags
    assert "implementation" in result.tags

    assert result.tags["python"].relations["code"] == 1
    assert result.tags["code"].relations["python"] == 1
    assert result.tags["python"].relations["implementation"] == 1
    assert result.tags["implementation"].relations["python"] == 1
    assert result.tags["code"].relations["implementation"] == 1
    assert result.tags["implementation"].relations["code"] == 1


def test_analyze_relations_independent() -> None:
    """Test that tag, heading, and body relations are computed independently."""
    nodes = node_from_org("* DONE Python tests :Python:Testing:\nPython code\n")

    result_tags = analyze(nodes, {}, category="tags", max_relations=3)
    # Tag relations: Python-Testing
    assert result_tags.tags["Python"].relations.get("Testing") == 1
    assert "tests" not in result_tags.tags["Python"].relations

    result_heading = analyze(nodes, {}, category="heading", max_relations=3)
    # Heading relations: python-tests (lowercase, normalized)
    assert result_heading.tags["python"].relations.get("tests") == 1
    assert "python" in result_heading.tags
    assert "Testing" not in result_heading.tags["python"].relations

    result_body = analyze(nodes, {}, category="body", max_relations=3)
    # Body relations: python-code (lowercase, normalized)
    assert result_body.tags["python"].relations.get("code") == 1


def test_analyze_relations_with_different_counts() -> None:
    """Test that different nodes with different counts increment correctly."""
    nodes = node_from_org("""
* DONE Task :TagA:TagB:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-18 Wed 09:05]
:END:

* TODO Task :TagA:TagB:
:LOGBOOK:
- State "DONE"       from "TODO"       [2023-10-20 Fri 09:15]
- State "DONE"       from "TODO"       [2023-10-19 Thu 09:10]
- State "DONE"       from "TODO"       [2023-10-18 Wed 09:05]
:END:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    # First node: count = max(1, 1) = 1
    # Second node: count = max(0, 3) = 3
    # Total: 1 + 3 = 4
    assert result.tags["TagA"].relations["TagB"] == 4
    assert result.tags["TagB"].relations["TagA"] == 4


def test_analyze_relations_mixed_tags() -> None:
    """Test relations with tasks that share some but not all tags."""
    nodes = node_from_org("""
* DONE Task :Python:Testing:
* DONE Task :Python:Debugging:
* DONE Task :Testing:Debugging:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    # Python appears with Testing (1x) and Debugging (1x)
    assert result.tags["Python"].relations["Testing"] == 1
    assert result.tags["Python"].relations["Debugging"] == 1

    # Testing appears with Python (1x) and Debugging (1x)
    assert result.tags["Testing"].relations["Python"] == 1
    assert result.tags["Testing"].relations["Debugging"] == 1

    # Debugging appears with Python (1x) and Testing (1x)
    assert result.tags["Debugging"].relations["Python"] == 1
    assert result.tags["Debugging"].relations["Testing"] == 1


def test_analyze_relations_empty_tags() -> None:
    """Test that tasks with no tags create no relations."""
    nodes = node_from_org("* DONE Task\nContent\n")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    assert result.tags == {}


def test_analyze_four_tags_six_relations() -> None:
    """Test task with four tags creates six bidirectional relations."""
    nodes = node_from_org("* DONE Task :A:B:C:D:\n")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    # With 4 tags, we should have C(4,2) = 6 unique pairs
    # A-B, A-C, A-D, B-C, B-D, C-D

    assert len(result.tags["A"].relations) == 3  # B, C, D
    assert len(result.tags["B"].relations) == 3  # A, C, D
    assert len(result.tags["C"].relations) == 3  # A, B, D
    assert len(result.tags["D"].relations) == 3  # A, B, C

    assert result.tags["A"].relations["B"] == 1
    assert result.tags["A"].relations["C"] == 1
    assert result.tags["A"].relations["D"] == 1
    assert result.tags["B"].relations["C"] == 1
    assert result.tags["B"].relations["D"] == 1
    assert result.tags["C"].relations["D"] == 1


def test_analyze_relations_result_structure() -> None:
    """Test that analyze returns Tags objects with correct structure."""

    from orgstats.analyze import Tag

    nodes = node_from_org("* DONE Task :Python:Testing:\n")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    assert isinstance(result.tags["Python"], Tag)
    assert result.tags["Python"].name == "Python"
    assert isinstance(result.tags["Python"].relations, dict)
    assert isinstance(result.tags["Python"].relations["Testing"], int)
