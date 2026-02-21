"""Tests for the analyze() function - integration tests only."""

import orgparse

from org.analyze import analyze
from tests.conftest import node_from_org


def test_analyze_empty_nodes() -> None:
    """Test analyze with empty nodes list."""
    nodes: list[orgparse.node.OrgNode] = []
    result = analyze(nodes, {}, category="tags", max_relations=3, category_property="CATEGORY")

    assert result.total_tasks == 0
    assert result.task_states.values.get("DONE", 0) == 0
    assert result.task_states.values.get("TODO", 0) == 0
    assert result.tags == {}


def test_analyze_single_done_task() -> None:
    """Test analyze with a single DONE task."""
    nodes = node_from_org("* DONE Write tests :Testing:\nUnit tests\n")

    result = analyze(nodes, {}, category="tags", max_relations=3, category_property="CATEGORY")

    assert result.total_tasks == 1
    assert result.task_states.values["DONE"] == 1
    assert result.task_states.values.get("TODO", 0) == 0
    assert "Testing" in result.tags
    assert result.tags["Testing"].total_tasks == 1


def test_analyze_multiple_tasks() -> None:
    """Test analyze with multiple tasks."""
    nodes = node_from_org("""
* DONE Task 1 :Tag1:
* DONE Task 2 :Tag2:
* TODO Task 3 :Tag1:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, category_property="CATEGORY")

    assert result.total_tasks == 3
    assert result.task_states.values["DONE"] == 2
    assert result.task_states.values["TODO"] == 1


def test_analyze_tag_frequencies() -> None:
    """Test analyze computes tag frequencies correctly."""
    nodes = node_from_org("""
* DONE Task 1 :Tag1:Tag2:
* DONE Task 2 :Tag2:Tag3:
* DONE Task 3 :Tag1:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, category_property="CATEGORY")

    assert result.tags["Tag1"].total_tasks == 2
    assert result.tags["Tag2"].total_tasks == 2
    assert result.tags["Tag3"].total_tasks == 1


def test_analyze_heading_word_frequencies() -> None:
    """Test analyze computes heading word frequencies correctly."""
    nodes = node_from_org("""
* DONE Task one
* DONE Task two
* DONE Another one
""")

    result = analyze(nodes, {}, category="heading", max_relations=3, category_property="CATEGORY")

    assert result.tags["one"].total_tasks == 2
    assert result.tags["two"].total_tasks == 1


def test_analyze_body_word_frequencies() -> None:
    """Test analyze computes body word frequencies correctly."""
    nodes = node_from_org("""
* DONE Task 1
This body text

* DONE Task 2
This body text
""")

    result = analyze(nodes, {}, category="body", max_relations=3, category_property="CATEGORY")

    assert result.tags["body"].total_tasks == 2
    assert result.tags["text"].total_tasks == 2


def test_analyze_with_custom_mapping() -> None:
    """Test analyze applies custom tag mapping."""
    mapping = {"oldtag": "newtag", "Tag1": "Tag2"}
    nodes = node_from_org("""
* DONE Task 1 :oldtag:
* DONE Task 2 :Tag1:
""")

    result = analyze(nodes, mapping, category="tags", max_relations=3, category_property="CATEGORY")

    assert "oldtag" not in result.tags
    assert "Tag1" not in result.tags
    assert result.tags["newtag"].total_tasks == 1
    assert result.tags["Tag2"].total_tasks == 1


def test_analyze_mapping_affects_all_categories() -> None:
    """Test mapping works across all categories."""
    mapping = {"fix": "bugfix"}
    nodes = node_from_org("* DONE fix the bug\nSome fix here\n")

    result_heading = analyze(
        nodes, mapping, category="heading", max_relations=3, category_property="CATEGORY"
    )
    result_body = analyze(
        nodes, mapping, category="body", max_relations=3, category_property="CATEGORY"
    )

    assert "fix" not in result_heading.tags
    assert "bugfix" in result_heading.tags
    assert "fix" not in result_body.tags
    assert "bugfix" in result_body.tags


def test_analyze_all_task_states_mixed() -> None:
    """Test analyze counts all different task states."""
    nodes = node_from_org("""
* DONE Completed task
* TODO Pending task
* DONE Another completed task
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, category_property="CATEGORY")

    assert result.total_tasks == 3
    assert result.task_states.values["DONE"] == 2
    assert result.task_states.values["TODO"] == 1


def test_analyze_accumulates_across_nodes() -> None:
    """Test analyze accumulates frequencies across multiple nodes."""
    nodes = node_from_org("""
* DONE Task :Tag1:Tag2:
* DONE Task :Tag2:Tag3:
* DONE Task :Tag1:Tag3:
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, category_property="CATEGORY")

    assert result.total_tasks == 3
    assert result.tags["Tag1"].total_tasks == 2
    assert result.tags["Tag2"].total_tasks == 2
    assert result.tags["Tag3"].total_tasks == 2


def test_analyze_state_counts_match_total_tasks() -> None:
    """Test sum of state counts equals total tasks."""
    nodes = node_from_org("""
* DONE Task 1
* TODO Task 2
* DONE Task 3
* CANCELLED Task 4
""")

    result = analyze(nodes, {}, category="tags", max_relations=3, category_property="CATEGORY")

    state_sum = sum(result.task_states.values.values())
    assert state_sum == result.total_tasks
    assert state_sum == 4
