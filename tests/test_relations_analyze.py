"""Tests for relations computation in the analyze() function."""

from typing import Any

from orgstats.core import analyze
from tests.conftest import node_from_org


def test_analyze_empty_nodes_has_empty_relations() -> None:
    """Test analyze with empty nodes returns empty relations."""
    nodes: list[Any] = []
    result = analyze(nodes, {}, category="tags", max_relations=3)

    assert result.tag_relations == {}


def test_analyze_single_tag_no_relations() -> None:
    """Test task with single tag creates no Relations objects."""
    nodes = node_from_org("* DONE Task :Python:\n")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    assert result.tag_relations == {}


def test_analyze_two_tags_bidirectional_relation() -> None:
    """Test task with two tags creates bidirectional relation."""
    nodes = node_from_org("* DONE Task :Python:Testing:\n")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    assert "python" in result.tag_relations
    assert "testing" in result.tag_relations

    assert result.tag_relations["python"].relations["testing"] == 1
    assert result.tag_relations["testing"].relations["python"] == 1


def test_analyze_three_tags_all_relations() -> None:
    """Test task with three tags creates all bidirectional relations."""
    nodes = node_from_org("* DONE Task :TagA:TagB:TagC:\n")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    assert "taga" in result.tag_relations
    assert "tagb" in result.tag_relations
    assert "tagc" in result.tag_relations

    assert result.tag_relations["taga"].relations["tagb"] == 1
    assert result.tag_relations["tagb"].relations["taga"] == 1
    assert result.tag_relations["taga"].relations["tagc"] == 1
    assert result.tag_relations["tagc"].relations["taga"] == 1
    assert result.tag_relations["tagb"].relations["tagc"] == 1
    assert result.tag_relations["tagc"].relations["tagb"] == 1

    assert len(result.tag_relations["taga"].relations) == 2
    assert len(result.tag_relations["tagb"].relations) == 2
    assert len(result.tag_relations["tagc"].relations) == 2


def test_analyze_no_self_relations() -> None:
    """Test that tags do not create relations with themselves."""
    nodes = node_from_org("* DONE Task :Python:Testing:\n")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    assert "python" not in result.tag_relations["python"].relations
    assert "testing" not in result.tag_relations["testing"].relations


def test_analyze_relations_normalized() -> None:
    """Test that tag normalization applies to relations."""
    nodes = node_from_org("* DONE Task :Test:SysAdmin:\n")

    result = analyze(
        nodes, {"test": "testing", "sysadmin": "devops"}, category="tags", max_relations=3
    )

    # "Test" -> "test" -> "testing" (mapped)
    # "SysAdmin" -> "sysadmin" -> "devops" (mapped)
    assert "testing" in result.tag_relations
    assert "devops" in result.tag_relations
    assert result.tag_relations["testing"].relations["devops"] == 1
    assert result.tag_relations["devops"].relations["testing"] == 1


def test_analyze_relations_accumulate() -> None:
    """Test that relations accumulate across multiple nodes."""
    nodes = node_from_org("""
* DONE Task :Python:Testing:
* DONE Task :Python:Testing:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    assert result.tag_relations["python"].relations["testing"] == 2
    assert result.tag_relations["testing"].relations["python"] == 2


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
    assert result.tag_relations["daily"].relations["meeting"] == 2
    assert result.tag_relations["meeting"].relations["daily"] == 2


def test_analyze_heading_relations() -> None:
    """Test that heading word relations are computed for heading category."""
    nodes = node_from_org("* DONE Implement feature\n")

    result = analyze(nodes, {}, category="heading", max_relations=3)

    assert "implement" in result.tag_relations
    assert "feature" in result.tag_relations
    assert result.tag_relations["implement"].relations["feature"] == 1
    assert result.tag_relations["feature"].relations["implement"] == 1


def test_analyze_body_relations() -> None:
    """Test that body word relations are computed for body category."""
    nodes = node_from_org("* DONE Task\nPython code implementation\n")

    result = analyze(nodes, {}, category="body", max_relations=3)

    assert "python" in result.tag_relations
    assert "code" in result.tag_relations
    assert "implementation" in result.tag_relations

    assert result.tag_relations["python"].relations["code"] == 1
    assert result.tag_relations["code"].relations["python"] == 1
    assert result.tag_relations["python"].relations["implementation"] == 1
    assert result.tag_relations["implementation"].relations["python"] == 1
    assert result.tag_relations["code"].relations["implementation"] == 1
    assert result.tag_relations["implementation"].relations["code"] == 1


def test_analyze_relations_independent() -> None:
    """Test that tag, heading, and body relations are computed independently."""
    nodes = node_from_org("* DONE Python tests :Python:Testing:\nPython code\n")

    result_tags = analyze(nodes, {}, category="tags", max_relations=3)
    # Tag relations: Python-Testing
    assert result_tags.tag_relations["python"].relations.get("testing") == 1
    assert "tests" not in result_tags.tag_relations["python"].relations

    result_heading = analyze(nodes, {}, category="heading", max_relations=3)
    # Heading relations: Python-tests
    assert result_heading.tag_relations["python"].relations.get("tests") == 1
    assert "python" in result_heading.tag_relations
    assert "testing" not in result_heading.tag_relations["python"].relations

    result_body = analyze(nodes, {}, category="body", max_relations=3)
    # Body relations: Python-code
    assert result_body.tag_relations["python"].relations.get("code") == 1


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
    assert result.tag_relations["taga"].relations["tagb"] == 4
    assert result.tag_relations["tagb"].relations["taga"] == 4


def test_analyze_relations_mixed_tags() -> None:
    """Test relations with tasks that share some but not all tags."""
    nodes = node_from_org("""
* DONE Task :Python:Testing:
* DONE Task :Python:Debugging:
* DONE Task :Testing:Debugging:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    # Python appears with Testing (1x) and Debugging (1x)
    assert result.tag_relations["python"].relations["testing"] == 1
    assert result.tag_relations["python"].relations["debugging"] == 1

    # Testing appears with Python (1x) and Debugging (1x)
    assert result.tag_relations["testing"].relations["python"] == 1
    assert result.tag_relations["testing"].relations["debugging"] == 1

    # Debugging appears with Python (1x) and Testing (1x)
    assert result.tag_relations["debugging"].relations["python"] == 1
    assert result.tag_relations["debugging"].relations["testing"] == 1


def test_analyze_relations_empty_tags() -> None:
    """Test that tasks with no tags create no relations."""
    nodes = node_from_org("* DONE Task\nContent\n")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    assert result.tag_relations == {}


def test_analyze_four_tags_six_relations() -> None:
    """Test task with four tags creates six bidirectional relations."""
    nodes = node_from_org("* DONE Task :A:B:C:D:\n")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    # With 4 tags, we should have C(4,2) = 6 unique pairs
    # A-B, A-C, A-D, B-C, B-D, C-D

    assert len(result.tag_relations["a"].relations) == 3  # B, C, D
    assert len(result.tag_relations["b"].relations) == 3  # A, C, D
    assert len(result.tag_relations["c"].relations) == 3  # A, B, D
    assert len(result.tag_relations["d"].relations) == 3  # A, B, C

    assert result.tag_relations["a"].relations["b"] == 1
    assert result.tag_relations["a"].relations["c"] == 1
    assert result.tag_relations["a"].relations["d"] == 1
    assert result.tag_relations["b"].relations["c"] == 1
    assert result.tag_relations["b"].relations["d"] == 1
    assert result.tag_relations["c"].relations["d"] == 1


def test_analyze_relations_result_structure() -> None:
    """Test that analyze returns Relations objects with correct structure."""
    from orgstats.core import Relations

    nodes = node_from_org("* DONE Task :Python:Testing:\n")

    result = analyze(nodes, {}, category="tags", max_relations=3)

    assert isinstance(result.tag_relations["python"], Relations)
    assert result.tag_relations["python"].name == "python"
    assert isinstance(result.tag_relations["python"].relations, dict)
    assert isinstance(result.tag_relations["python"].relations["testing"], int)
