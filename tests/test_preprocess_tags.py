"""Tests for tags-as-category preprocessing."""

from org.filters import preprocess_tags_as_category
from tests.conftest import node_from_org


def test_preprocess_single_tag_sets_category() -> None:
    """Single tag should become heading category."""
    nodes = node_from_org("* DONE Task :work:\n")

    processed = preprocess_tags_as_category(nodes)

    assert len(processed) == 1
    assert str(processed[0].category) == "work"


def test_preprocess_multiple_tags_uses_first() -> None:
    """First effective tag should be used as category."""
    nodes = node_from_org("* DONE Task :bug:feature:enhancement:\n")

    processed = preprocess_tags_as_category(nodes)

    assert len(processed) == 1
    assert str(processed[0].category) == "bug"


def test_preprocess_no_tags_keeps_null_category() -> None:
    """Nodes without tags should keep null category."""
    nodes = node_from_org("* DONE Task without tags\n")

    processed = preprocess_tags_as_category(nodes)

    assert len(processed) == 1
    assert processed[0].category is None


def test_preprocess_preserves_heading_and_body() -> None:
    """Preprocessing should preserve heading text and body text."""
    nodes = node_from_org(
        """* DONE Important Task :work:

Task body content here.
"""
    )

    processed = preprocess_tags_as_category(nodes)

    assert len(processed) == 1
    assert processed[0].title_text.strip() == "Important Task"
    assert "Task body content" in processed[0].body_text


def test_preprocess_preserves_todo_state() -> None:
    """Preprocessing should preserve TODO state."""
    nodes = node_from_org("* TODO Incomplete task :work:\n")

    processed = preprocess_tags_as_category(nodes)

    assert len(processed) == 1
    assert processed[0].todo == "TODO"
    assert str(processed[0].category) == "work"
