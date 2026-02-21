"""Tests for combined preprocessing (gamify + tags)."""

from orgstats.filters import preprocess_gamify_categories, preprocess_tags_as_category
from tests.conftest import node_from_org


def test_both_preprocessors_tags_wins() -> None:
    """Test that tags override gamify when both are enabled."""
    nodes = node_from_org("""
* DONE Task :work:
:PROPERTIES:
:gamify_exp: 5
:END:
""")

    nodes = preprocess_gamify_categories(nodes, "CATEGORY")
    nodes = preprocess_tags_as_category(nodes, "CATEGORY")

    assert len(nodes) == 1
    assert nodes[0].properties.get("CATEGORY") == "work"


def test_gamify_then_tags_without_tags_preserves_gamify() -> None:
    """Test that gamify category is preserved for tasks without tags."""
    nodes = node_from_org("""
* DONE Task without tags
:PROPERTIES:
:gamify_exp: 5
:END:
""")

    nodes = preprocess_gamify_categories(nodes, "CATEGORY")
    nodes = preprocess_tags_as_category(nodes, "CATEGORY")

    assert len(nodes) == 1
    assert nodes[0].properties.get("CATEGORY") == "simple"


def test_gamify_only() -> None:
    """Test gamify preprocessing alone."""
    nodes = node_from_org("""
* DONE Task :work:
:PROPERTIES:
:gamify_exp: 25
:END:
""")

    nodes = preprocess_gamify_categories(nodes, "CATEGORY")

    assert len(nodes) == 1
    assert nodes[0].properties.get("CATEGORY") == "hard"


def test_tags_only() -> None:
    """Test tags preprocessing alone."""
    nodes = node_from_org("""
* DONE Task :work:
:PROPERTIES:
:gamify_exp: 25
:END:
""")

    nodes = preprocess_tags_as_category(nodes, "CATEGORY")

    assert len(nodes) == 1
    assert nodes[0].properties.get("CATEGORY") == "work"


def test_neither_preprocessor() -> None:
    """Test no preprocessing results in no CATEGORY property."""
    nodes = node_from_org("""
* DONE Task :work:
:PROPERTIES:
:gamify_exp: 25
:END:
""")

    assert len(nodes) == 1
    assert nodes[0].properties.get("CATEGORY") is None


def test_multiple_nodes_mixed_processing() -> None:
    """Test processing multiple nodes with different tag scenarios."""
    nodes = node_from_org("""
* DONE Task 1 :work:
:PROPERTIES:
:gamify_exp: 5
:END:

* DONE Task 2
:PROPERTIES:
:gamify_exp: 25
:END:

* DONE Task 3 :bug:
:PROPERTIES:
:gamify_exp: 15
:END:
""")

    nodes = preprocess_gamify_categories(nodes, "CATEGORY")
    nodes = preprocess_tags_as_category(nodes, "CATEGORY")

    assert len(nodes) == 3
    assert nodes[0].properties.get("CATEGORY") == "work"
    assert nodes[1].properties.get("CATEGORY") == "hard"
    assert nodes[2].properties.get("CATEGORY") == "bug"


def test_custom_category_property_both() -> None:
    """Test both preprocessors with custom category property."""
    nodes = node_from_org("""
* DONE Task :work:
:PROPERTIES:
:gamify_exp: 5
:END:
""")

    nodes = preprocess_gamify_categories(nodes, "TASK_TYPE")
    nodes = preprocess_tags_as_category(nodes, "TASK_TYPE")

    assert len(nodes) == 1
    assert nodes[0].properties.get("TASK_TYPE") == "work"
    assert nodes[0].properties.get("CATEGORY") is None


def test_tags_override_all_gamify_categories() -> None:
    """Test tags override simple, regular, and hard gamify categories."""
    nodes_simple = node_from_org("""
* DONE Task :urgent:
:PROPERTIES:
:gamify_exp: 5
:END:
""")

    nodes_regular = node_from_org("""
* DONE Task :urgent:
:PROPERTIES:
:gamify_exp: 15
:END:
""")

    nodes_hard = node_from_org("""
* DONE Task :urgent:
:PROPERTIES:
:gamify_exp: 25
:END:
""")

    nodes_simple = preprocess_gamify_categories(nodes_simple, "CATEGORY")
    nodes_simple = preprocess_tags_as_category(nodes_simple, "CATEGORY")

    nodes_regular = preprocess_gamify_categories(nodes_regular, "CATEGORY")
    nodes_regular = preprocess_tags_as_category(nodes_regular, "CATEGORY")

    nodes_hard = preprocess_gamify_categories(nodes_hard, "CATEGORY")
    nodes_hard = preprocess_tags_as_category(nodes_hard, "CATEGORY")

    assert nodes_simple[0].properties.get("CATEGORY") == "urgent"
    assert nodes_regular[0].properties.get("CATEGORY") == "urgent"
    assert nodes_hard[0].properties.get("CATEGORY") == "urgent"
