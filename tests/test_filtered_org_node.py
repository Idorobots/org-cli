"""Unit tests for _FilteredOrgNode performance optimization."""

from datetime import date

from org.filters import _filter_node_repeats, _FilteredOrgNode
from tests.conftest import node_from_org


def test_filtered_org_node_overrides_repeated_tasks() -> None:
    """Test that _FilteredOrgNode returns the filtered repeated_tasks list."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""
    nodes = node_from_org(org_text)
    original_node = nodes[0]

    filtered_node = _FilteredOrgNode(original_node, [original_node.repeated_tasks[0]])

    assert len(filtered_node.repeated_tasks) == 1
    assert filtered_node.repeated_tasks[0] == original_node.repeated_tasks[0]


def test_filtered_org_node_delegates_heading() -> None:
    """Test that _FilteredOrgNode delegates heading to the original node."""
    org_text = """* DONE My Task Title
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""
    nodes = node_from_org(org_text)
    original_node = nodes[0]

    filtered_node = _FilteredOrgNode(original_node, [original_node.repeated_tasks[0]])

    assert filtered_node.heading == "My Task Title"
    assert filtered_node.heading == original_node.heading


def test_filtered_org_node_delegates_todo() -> None:
    """Test that _FilteredOrgNode delegates todo state to the original node."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
:END:
"""
    nodes = node_from_org(org_text)
    original_node = nodes[0]

    filtered_node = _FilteredOrgNode(original_node, [original_node.repeated_tasks[0]])

    assert filtered_node.todo == "DONE"
    assert filtered_node.todo == original_node.todo


def test_filtered_org_node_delegates_tags() -> None:
    """Test that _FilteredOrgNode delegates tags to the original node."""
    org_text = """* DONE Task :tag1:tag2:
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
:END:
"""
    nodes = node_from_org(org_text)
    original_node = nodes[0]

    filtered_node = _FilteredOrgNode(original_node, [original_node.repeated_tasks[0]])

    assert filtered_node.tags == {"tag1", "tag2"}
    assert filtered_node.tags == original_node.tags


def test_filtered_org_node_delegates_properties() -> None:
    """Test that _FilteredOrgNode delegates properties to the original node."""
    org_text = """* DONE Task
:PROPERTIES:
:gamify_exp: 15
:custom_prop: value
:END:
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
:END:
"""
    nodes = node_from_org(org_text)
    original_node = nodes[0]

    filtered_node = _FilteredOrgNode(original_node, [original_node.repeated_tasks[0]])

    assert filtered_node.properties.get("gamify_exp") == "15"
    assert filtered_node.properties.get("custom_prop") == "value"
    assert filtered_node.properties == original_node.properties


def test_filtered_org_node_delegates_body() -> None:
    """Test that _FilteredOrgNode delegates body to the original node."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
:END:
This is the body of the task.
"""
    nodes = node_from_org(org_text)
    original_node = nodes[0]

    filtered_node = _FilteredOrgNode(original_node, [original_node.repeated_tasks[0]])

    assert "This is the body of the task." in filtered_node.body
    assert filtered_node.body == original_node.body


def test_filtered_org_node_does_not_mutate_original() -> None:
    """Test that _FilteredOrgNode does not mutate the original node's repeated_tasks."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
- State "DONE" from "TODO" [2025-03-20 Thu 14:00]
:END:
"""
    nodes = node_from_org(org_text)
    original_node = nodes[0]
    original_repeat_count = len(original_node.repeated_tasks)

    filtered_node = _FilteredOrgNode(original_node, [original_node.repeated_tasks[0]])

    assert len(original_node.repeated_tasks) == original_repeat_count
    assert len(filtered_node.repeated_tasks) == 1


def test_filtered_org_node_with_empty_filtered_list() -> None:
    """Test that _FilteredOrgNode works with an empty filtered list."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
:END:
"""
    nodes = node_from_org(org_text)
    original_node = nodes[0]

    filtered_node = _FilteredOrgNode(original_node, [])

    assert len(filtered_node.repeated_tasks) == 0
    assert filtered_node.heading == original_node.heading


def test_filtered_org_node_with_single_repeat() -> None:
    """Test that _FilteredOrgNode works correctly with a single repeat."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""
    nodes = node_from_org(org_text)
    original_node = nodes[0]

    filtered_node = _FilteredOrgNode(original_node, [original_node.repeated_tasks[1]])

    assert len(filtered_node.repeated_tasks) == 1
    assert filtered_node.repeated_tasks[0].start.date() == date(2025, 2, 15)  # type: ignore[attr-defined]


def test_filtered_org_node_preserves_repeat_attributes() -> None:
    """Test that _FilteredOrgNode preserves repeated task attributes."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
:END:
"""
    nodes = node_from_org(org_text)
    original_node = nodes[0]
    original_repeat = original_node.repeated_tasks[0]

    filtered_node = _FilteredOrgNode(original_node, [original_repeat])

    filtered_repeat = filtered_node.repeated_tasks[0]
    assert filtered_repeat.start == original_repeat.start
    assert filtered_repeat.after == original_repeat.after
    assert filtered_repeat.before == original_repeat.before


def test_filter_node_repeats_returns_filtered_node() -> None:
    """Test that _filter_node_repeats returns _FilteredOrgNode when some repeats match."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "TODO" from "DONE" [2025-02-15 Sat 11:00]
:END:
"""
    nodes = node_from_org(org_text, todo_keys=["TODO"])
    node = nodes[0]

    filtered_node = _filter_node_repeats(node, lambda rt: rt.after == "DONE")

    assert filtered_node is not None
    assert isinstance(filtered_node, _FilteredOrgNode)
    assert len(filtered_node.repeated_tasks) == 1
    assert filtered_node.repeated_tasks[0].after == "DONE"


def test_filter_node_repeats_returns_original_when_all_match() -> None:
    """Test that _filter_node_repeats returns original node when all repeats match."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""
    nodes = node_from_org(org_text)
    node = nodes[0]

    filtered_node = _filter_node_repeats(node, lambda rt: rt.after == "DONE")

    assert filtered_node is node
    assert len(filtered_node.repeated_tasks) == 2


def test_filter_node_repeats_returns_none_when_none_match() -> None:
    """Test that _filter_node_repeats returns None when no repeats match."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""
    nodes = node_from_org(org_text)
    node = nodes[0]

    filtered_node = _filter_node_repeats(node, lambda rt: rt.after == "CANCELLED")

    assert filtered_node is None


def test_filter_node_repeats_returns_original_when_no_repeats() -> None:
    """Test that _filter_node_repeats returns original node when no repeated_tasks."""
    nodes = node_from_org("* DONE Task\n")
    node = nodes[0]

    filtered_node = _filter_node_repeats(node, lambda rt: rt.after == "DONE")

    assert filtered_node is node
    assert len(filtered_node.repeated_tasks) == 0


def test_filtered_org_node_is_instance_of_orgnode() -> None:
    """Test that _FilteredOrgNode is recognized as an instance of OrgNode."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
:END:
"""
    nodes = node_from_org(org_text)
    original_node = nodes[0]

    filtered_node = _FilteredOrgNode(original_node, [original_node.repeated_tasks[0]])

    assert isinstance(filtered_node, type(original_node).__bases__[0])


def test_filtered_org_node_independent_from_original() -> None:
    """Test that modifying filtered node's list doesn't affect original."""
    org_text = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-02-15 Sat 11:00]
:END:
"""
    nodes = node_from_org(org_text)
    original_node = nodes[0]
    original_count = len(original_node.repeated_tasks)

    filtered_list = [original_node.repeated_tasks[0]]
    filtered_node = _FilteredOrgNode(original_node, filtered_list)

    filtered_list.clear()

    assert len(original_node.repeated_tasks) == original_count
    assert len(filtered_node.repeated_tasks) == 0
