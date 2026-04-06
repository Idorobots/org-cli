"""Unit tests for repeat filtering behavior."""

from datetime import date

from org.filters import _filter_node_repeats
from tests.conftest import node_from_org


def test_filter_node_repeats_returns_original_when_no_repeats() -> None:
    """Nodes without repeats should pass through unchanged."""
    node = node_from_org("* DONE Task\n")[0]

    filtered = _filter_node_repeats(node, lambda repeat: repeat.after == "DONE")

    assert filtered is node
    assert len(node.repeats) == 0


def test_filter_node_repeats_returns_original_when_all_match() -> None:
    """Nodes should pass through unchanged when all repeats match."""
    node = node_from_org(
        """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""
    )[0]

    filtered = _filter_node_repeats(node, lambda repeat: repeat.after == "DONE")

    assert filtered is node
    assert len(node.repeats) == 2


def test_filter_node_repeats_returns_none_when_none_match() -> None:
    """Nodes should be excluded when no repeat entry matches."""
    node = node_from_org(
        """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""
    )[0]

    filtered = _filter_node_repeats(node, lambda repeat: repeat.after == "CANCELLED")

    assert filtered is None


def test_filter_node_repeats_filters_in_place() -> None:
    """Nodes should keep only matching repeats and mutate in place."""
    node = node_from_org(
        """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "TODO" from "DONE" [2025-02-15 Sat 11:00]
:END:
""",
        todo_states=["TODO"],
    )[0]

    filtered = _filter_node_repeats(node, lambda repeat: repeat.after == "DONE")

    assert filtered is node
    assert len(node.repeats) == 1
    assert node.repeats[0].timestamp.start.date() == date(2025, 1, 10)


def test_filter_node_repeats_preserves_node_fields() -> None:
    """Filtering repeats should keep the rest of heading data unchanged."""
    node = node_from_org(
        """* DONE My Task :tag1:tag2:
:PROPERTIES:
:custom_prop: value
:END:
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "TODO" from "DONE" [2025-02-15 Sat 11:00]
:END:

Task body text.
""",
        todo_states=["TODO"],
    )[0]

    filtered = _filter_node_repeats(node, lambda repeat: repeat.after == "DONE")

    assert filtered is node
    assert node.title_text.strip() == "My Task"
    assert node.todo == "DONE"
    assert "tag1" in node.tags
    assert str(node.properties.get("custom_prop")) == "value"
    assert "Task body text." in node.body_text
