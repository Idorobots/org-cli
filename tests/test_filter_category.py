"""Tests for filter_category function."""

from org.filters import filter_category, preprocess_gamify_categories
from tests.conftest import node_from_org


def test_filter_category_matches_value() -> None:
    """Test filtering by exact category match."""
    nodes = node_from_org("""
* DONE Task 1
:PROPERTIES:
:CATEGORY: simple
:END:

* DONE Task 2
:PROPERTIES:
:CATEGORY: hard
:END:

* DONE Task 3
:PROPERTIES:
:CATEGORY: simple
:END:
""")

    filtered = filter_category(nodes, "CATEGORY", "simple")

    assert len(filtered) == 2
    assert filtered[0].heading == "Task 1"
    assert filtered[1].heading == "Task 3"


def test_filter_category_none_matches_missing() -> None:
    """Test filtering by 'none' matches nodes without property."""
    nodes = node_from_org("""
* DONE Task 1
:PROPERTIES:
:CATEGORY: simple
:END:

* DONE Task 2

* DONE Task 3
:PROPERTIES:
:CATEGORY: hard
:END:
""")

    filtered = filter_category(nodes, "CATEGORY", "none")

    assert len(filtered) == 1
    assert filtered[0].heading == "Task 2"


def test_filter_category_none_matches_empty_string() -> None:
    """Test filtering by 'none' matches empty property value."""
    nodes = node_from_org("""
* DONE Task 1
:PROPERTIES:
:CATEGORY: simple
:END:

* DONE Task 2
:PROPERTIES:
:CATEGORY:
:END:

* DONE Task 3
""")

    filtered = filter_category(nodes, "CATEGORY", "none")

    assert len(filtered) == 2
    assert filtered[0].heading == "Task 2"
    assert filtered[1].heading == "Task 3"


def test_filter_category_custom_property_name() -> None:
    """Test filtering with custom category property name."""
    nodes = node_from_org("""
* DONE Task 1
:PROPERTIES:
:TASK_TYPE: simple
:END:

* DONE Task 2
:PROPERTIES:
:TASK_TYPE: hard
:END:
""")

    filtered = filter_category(nodes, "TASK_TYPE", "simple")

    assert len(filtered) == 1
    assert filtered[0].heading == "Task 1"


def test_filter_category_no_matches() -> None:
    """Test filtering when no nodes match."""
    nodes = node_from_org("""
* DONE Task 1
:PROPERTIES:
:CATEGORY: simple
:END:

* DONE Task 2
:PROPERTIES:
:CATEGORY: regular
:END:
""")

    filtered = filter_category(nodes, "CATEGORY", "hard")

    assert len(filtered) == 0


def test_filter_category_all_match() -> None:
    """Test filtering when all nodes match."""
    nodes = node_from_org("""
* DONE Task 1
:PROPERTIES:
:CATEGORY: simple
:END:

* DONE Task 2
:PROPERTIES:
:CATEGORY: simple
:END:
""")

    filtered = filter_category(nodes, "CATEGORY", "simple")

    assert len(filtered) == 2


def test_filter_category_case_sensitive() -> None:
    """Test filtering is case-sensitive."""
    nodes = node_from_org("""
* DONE Task 1
:PROPERTIES:
:CATEGORY: Simple
:END:

* DONE Task 2
:PROPERTIES:
:CATEGORY: simple
:END:
""")

    filtered = filter_category(nodes, "CATEGORY", "simple")

    assert len(filtered) == 1
    assert filtered[0].heading == "Task 2"


def test_filter_category_with_preprocessed_nodes() -> None:
    """Test filtering after preprocessing with gamify."""
    nodes = node_from_org("""
* DONE Task 1
:PROPERTIES:
:gamify_exp: 5
:END:

* DONE Task 2
:PROPERTIES:
:gamify_exp: 15
:END:

* DONE Task 3
:PROPERTIES:
:gamify_exp: 25
:END:
""")

    preprocessed = preprocess_gamify_categories(nodes, "CATEGORY")
    filtered = filter_category(preprocessed, "CATEGORY", "simple")

    assert len(filtered) == 1
    assert filtered[0].heading == "Task 1"


def test_filter_category_empty_nodes() -> None:
    """Test filtering empty nodes list."""
    nodes = node_from_org("")

    filtered = filter_category(nodes, "CATEGORY", "simple")

    assert len(filtered) == 0


def test_filter_category_custom_values() -> None:
    """Test filtering with custom category values."""
    nodes = node_from_org("""
* DONE Task 1
:PROPERTIES:
:CATEGORY: urgent
:END:

* DONE Task 2
:PROPERTIES:
:CATEGORY: backlog
:END:

* DONE Task 3
:PROPERTIES:
:CATEGORY: urgent
:END:
""")

    filtered = filter_category(nodes, "CATEGORY", "urgent")

    assert len(filtered) == 2
    assert filtered[0].heading == "Task 1"
    assert filtered[1].heading == "Task 3"


def test_filter_category_preserves_properties() -> None:
    """Test that filtering preserves node properties."""
    nodes = node_from_org("""
* DONE Task
:PROPERTIES:
:CATEGORY: simple
:other_prop: value
:END:
""")

    filtered = filter_category(nodes, "CATEGORY", "simple")

    assert len(filtered) == 1
    assert filtered[0].properties.get("CATEGORY") == "simple"
    assert filtered[0].properties.get("other_prop") == "value"


def test_filter_category_preserves_tags() -> None:
    """Test that filtering preserves node tags."""
    nodes = node_from_org("""
* DONE Task :tag1:tag2:
:PROPERTIES:
:CATEGORY: simple
:END:
""")

    filtered = filter_category(nodes, "CATEGORY", "simple")

    assert len(filtered) == 1
    assert "tag1" in filtered[0].tags
    assert "tag2" in filtered[0].tags
