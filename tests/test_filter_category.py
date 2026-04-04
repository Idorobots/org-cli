"""Tests for filter_category function."""

from org.filters import filter_category
from tests.conftest import node_from_org


def test_filter_category_matches_value() -> None:
    """Filter by effective heading category value."""
    nodes = node_from_org(
        """* DONE Task 1
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
"""
    )

    filtered = filter_category(nodes, "simple")

    assert len(filtered) == 2
    assert filtered[0].title_text == "Task 1"
    assert filtered[1].title_text == "Task 3"


def test_filter_category_null_matches_missing_or_empty() -> None:
    """Filter by null category for missing/empty values."""
    nodes = node_from_org(
        """* DONE Task 1
:PROPERTIES:
:CATEGORY: simple
:END:

* DONE Task 2

* DONE Task 3
:PROPERTIES:
:CATEGORY:
:END:
"""
    )

    filtered = filter_category(nodes, "null")

    assert len(filtered) == 2
    assert filtered[0].title_text == "Task 2"
    assert filtered[1].title_text == "Task 3"


def test_filter_category_preserves_node_data() -> None:
    """Filtering by category should not change heading content."""
    nodes = node_from_org(
        """* DONE Task :tag1:tag2:
:PROPERTIES:
:CATEGORY: simple
:custom_prop: value
:END:
"""
    )

    filtered = filter_category(nodes, "simple")

    assert len(filtered) == 1
    assert "tag1" in filtered[0].tags
    assert str(filtered[0].properties.get("custom_prop")) == "value"
