"""Tests for tags-as-category preprocessing."""

from orgstats.filters import preprocess_tags_as_category
from tests.conftest import node_from_org


def test_preprocess_single_tag() -> None:
    """Test preprocessing with single tag sets category to that tag."""
    nodes = node_from_org("""
* DONE Task :work:
:PROPERTIES:
:END:
""")

    processed = preprocess_tags_as_category(nodes, "CATEGORY")

    assert len(processed) == 1
    assert processed[0].properties.get("CATEGORY") == "work"


def test_preprocess_multiple_tags_uses_first() -> None:
    """Test preprocessing with multiple tags uses first tag."""
    nodes = node_from_org("""
* DONE Task :bug:feature:enhancement:
:PROPERTIES:
:END:
""")

    processed = preprocess_tags_as_category(nodes, "CATEGORY")

    assert len(processed) == 1
    assert processed[0].properties.get("CATEGORY") == "bug"


def test_preprocess_no_tags_no_category() -> None:
    """Test preprocessing without tags doesn't set category."""
    nodes = node_from_org("""
* DONE Task without tags
:PROPERTIES:
:END:
""")

    processed = preprocess_tags_as_category(nodes, "CATEGORY")

    assert len(processed) == 1
    assert processed[0].properties.get("CATEGORY") is None


def test_preprocess_empty_tags() -> None:
    """Test preprocessing with empty tags set."""
    nodes = node_from_org("* DONE Task\n")

    processed = preprocess_tags_as_category(nodes, "CATEGORY")

    assert len(processed) == 1
    assert processed[0].properties.get("CATEGORY") is None


def test_preprocess_custom_category_property() -> None:
    """Test preprocessing with custom property name."""
    nodes = node_from_org("""
* DONE Task :work:
:PROPERTIES:
:END:
""")

    processed = preprocess_tags_as_category(nodes, "TAG_TYPE")

    assert len(processed) == 1
    assert processed[0].properties.get("TAG_TYPE") == "work"
    assert processed[0].properties.get("CATEGORY") is None


def test_preprocess_preserves_other_properties() -> None:
    """Test preprocessing preserves other node properties."""
    nodes = node_from_org("""
* DONE Task :work:
:PROPERTIES:
:other_prop: value
:gamify_exp: 15
:END:
""")

    processed = preprocess_tags_as_category(nodes, "CATEGORY")

    assert len(processed) == 1
    assert processed[0].properties.get("CATEGORY") == "work"
    assert processed[0].properties.get("other_prop") == "value"
    assert processed[0].properties.get("gamify_exp") == "15"


def test_preprocess_preserves_heading() -> None:
    """Test preprocessing preserves node heading."""
    nodes = node_from_org("""
* DONE Important Task :work:
:PROPERTIES:
:END:
""")

    processed = preprocess_tags_as_category(nodes, "CATEGORY")

    assert len(processed) == 1
    assert processed[0].heading == "Important Task"


def test_preprocess_preserves_body() -> None:
    """Test preprocessing preserves node body."""
    nodes = node_from_org("""
* DONE Task :work:
:PROPERTIES:
:END:

Task body content here.
""")

    processed = preprocess_tags_as_category(nodes, "CATEGORY")

    assert len(processed) == 1
    assert processed[0].properties.get("CATEGORY") == "work"
    assert "Task body content" in processed[0].body


def test_preprocess_tag_order_preserved() -> None:
    """Test that first tag respects org file order."""
    nodes = node_from_org("""
* DONE Task :zebra:alpha:beta:
:PROPERTIES:
:END:
""")

    processed = preprocess_tags_as_category(nodes, "CATEGORY")

    assert len(processed) == 1
    assert processed[0].properties.get("CATEGORY") == "zebra"


def test_preprocess_overwrites_existing_category() -> None:
    """Test preprocessing overwrites existing category property."""
    nodes = node_from_org("""
* DONE Task :work:
:PROPERTIES:
:CATEGORY: old_value
:END:
""")

    processed = preprocess_tags_as_category(nodes, "CATEGORY")

    assert len(processed) == 1
    assert processed[0].properties.get("CATEGORY") == "work"


def test_preprocess_multiple_nodes() -> None:
    """Test preprocessing multiple nodes correctly."""
    nodes = node_from_org("""
* DONE Task 1 :work:
:PROPERTIES:
:END:

* DONE Task 2 :bug:
:PROPERTIES:
:END:

* DONE Task 3 :feature:
:PROPERTIES:
:END:
""")

    processed = preprocess_tags_as_category(nodes, "CATEGORY")

    assert len(processed) == 3
    assert processed[0].properties.get("CATEGORY") == "work"
    assert processed[1].properties.get("CATEGORY") == "bug"
    assert processed[2].properties.get("CATEGORY") == "feature"


def test_preprocess_mixed_nodes() -> None:
    """Test preprocessing nodes with and without tags."""
    nodes = node_from_org("""
* DONE Task with tag :work:
:PROPERTIES:
:END:

* DONE Task without tag
:PROPERTIES:
:END:

* DONE Another tagged task :bug:
:PROPERTIES:
:END:
""")

    processed = preprocess_tags_as_category(nodes, "CATEGORY")

    assert len(processed) == 3
    assert processed[0].properties.get("CATEGORY") == "work"
    assert processed[1].properties.get("CATEGORY") is None
    assert processed[2].properties.get("CATEGORY") == "bug"


def test_preprocess_empty_nodes() -> None:
    """Test preprocessing empty nodes list."""
    nodes = node_from_org("")

    processed = preprocess_tags_as_category(nodes, "CATEGORY")

    assert len(processed) == 0


def test_preprocess_tag_with_special_characters() -> None:
    """Test preprocessing preserves underscores in tags."""
    nodes = node_from_org("""
* DONE Task :my_tag:other_tag:tag123:
:PROPERTIES:
:END:
""")

    processed = preprocess_tags_as_category(nodes, "CATEGORY")

    assert len(processed) == 1
    assert processed[0].properties.get("CATEGORY") == "my_tag"


def test_preprocess_preserves_todo_state() -> None:
    """Test preprocessing preserves TODO state."""
    nodes = node_from_org("""
* TODO Incomplete task :work:
:PROPERTIES:
:END:
""")

    processed = preprocess_tags_as_category(nodes, "CATEGORY")

    assert len(processed) == 1
    assert processed[0].properties.get("CATEGORY") == "work"
    assert processed[0].todo == "TODO"


def test_preprocess_case_sensitive_tags() -> None:
    """Test that tag case is preserved."""
    nodes = node_from_org("""
* DONE Task :WorkTag:
:PROPERTIES:
:END:
""")

    processed = preprocess_tags_as_category(nodes, "CATEGORY")

    assert len(processed) == 1
    assert processed[0].properties.get("CATEGORY") == "WorkTag"
