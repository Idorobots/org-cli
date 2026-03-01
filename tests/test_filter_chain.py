"""Integration tests for filter chain and combinations."""

from datetime import datetime

from org.filters import (
    filter_completed,
    filter_date_from,
    filter_date_until,
    filter_property,
    filter_repeats_above,
    filter_tag,
)
from tests.conftest import node_from_org


def test_combining_repeats_and_date_filters() -> None:
    """Repeat and date filters should compose in sequence."""
    org_text_low = "* DONE Task\nCLOSED: [2025-01-20 Mon 10:00]\n"
    org_text_high = """* DONE Task
:LOGBOOK:
- State "DONE" from "TODO" [2025-02-10 Mon 09:00]
- State "DONE" from "TODO" [2025-02-12 Wed 11:00]
:END:
"""
    nodes = node_from_org(org_text_low) + node_from_org(org_text_high)

    result = filter_repeats_above(nodes, 1)
    result = filter_date_from(result, datetime(2025, 2, 1))

    assert len(result) == 1
    assert result[0] == nodes[1]


def test_combining_tag_and_property_filters() -> None:
    """Tag and property filters should apply as AND conditions."""
    nodes = (
        node_from_org("* DONE Task :tag1:\n:PROPERTIES:\n:custom_prop: value1\n:END:\n")
        + node_from_org("* DONE Task :tag1:\n:PROPERTIES:\n:custom_prop: value2\n:END:\n")
        + node_from_org("* DONE Task :tag2:\n:PROPERTIES:\n:custom_prop: value1\n:END:\n")
    )

    result = filter_tag(nodes, "tag1")
    result = filter_property(result, "custom_prop", "value1")

    assert len(result) == 1
    assert result[0] == nodes[0]


def test_multiple_property_filters_and_logic() -> None:
    """Multiple property filters should compose with AND behavior."""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:prop1: value1\n:prop2: value2\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:prop1: value1\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:prop2: value2\n:END:\n")
    )

    result = filter_property(nodes, "prop1", "value1")
    result = filter_property(result, "prop2", "value2")

    assert len(result) == 1
    assert result[0] == nodes[0]


def test_multiple_tag_filters_and_logic() -> None:
    """Multiple tag filters should compose with AND behavior."""
    nodes = (
        node_from_org("* DONE Task :tag1:tag2:\n")
        + node_from_org("* DONE Task :tag1:\n")
        + node_from_org("* DONE Task :tag2:\n")
    )

    result = filter_tag(nodes, "tag1")
    result = filter_tag(result, "tag2")

    assert len(result) == 1
    assert result[0] == nodes[0]


def test_combining_completion_and_repeats_filters() -> None:
    """Completion and repeat filters should compose correctly."""
    nodes = (
        node_from_org("* DONE Task\n")
        + node_from_org("* TODO Task\n")
        + node_from_org(
            "* DONE Task\n:LOGBOOK:\n"
            '- State "DONE" from "TODO" [2025-01-12 Sun 11:00]\n'
            '- State "DONE" from "TODO" [2025-01-13 Mon 11:00]\n'
            ":END:\n"
        )
    )

    result = filter_completed(nodes)
    result = filter_repeats_above(result, 1)

    assert len(result) == 1
    assert result[0] == nodes[2]


def test_date_range_filter() -> None:
    """Date from/until should compose as a bounded range."""
    org_text_jan = "* DONE Task\nCLOSED: [2025-01-15 Wed 10:00]\n"
    org_text_feb = "* DONE Task\nCLOSED: [2025-02-15 Sat 10:00]\n"
    org_text_mar = "* DONE Task\nCLOSED: [2025-03-15 Sat 10:00]\n"

    nodes = node_from_org(org_text_jan) + node_from_org(org_text_feb) + node_from_org(org_text_mar)

    result = filter_date_from(nodes, datetime(2025, 1, 31))
    result = filter_date_until(result, datetime(2025, 3, 1))

    assert len(result) == 1
    assert result[0] == nodes[1]


def test_filter_order_matters_not_result_for_pure_filters() -> None:
    """Reordering pure filters should preserve final matching set."""
    nodes = (
        node_from_org("* DONE Task :tag1:\n:PROPERTIES:\n:custom_prop: keep\n:END:\n")
        + node_from_org("* DONE Task :tag2:\n:PROPERTIES:\n:custom_prop: keep\n:END:\n")
        + node_from_org("* DONE Task :tag1:\n:PROPERTIES:\n:custom_prop: drop\n:END:\n")
    )

    result1 = filter_tag(nodes, "tag1")
    result1 = filter_property(result1, "custom_prop", "keep")

    result2 = filter_property(nodes, "custom_prop", "keep")
    result2 = filter_tag(result2, "tag1")

    assert len(result1) == len(result2)
    assert result1[0] == result2[0]


def test_all_filters_with_empty_input() -> None:
    """Filters should return empty output for empty input."""
    import orgparse

    empty_nodes: list[orgparse.node.OrgNode] = []

    assert filter_repeats_above(empty_nodes, 1) == []
    assert filter_date_from(empty_nodes, datetime(2025, 1, 1)) == []
    assert filter_date_until(empty_nodes, datetime(2025, 12, 31)) == []
    assert filter_property(empty_nodes, "prop", "value") == []
    assert filter_tag(empty_nodes, "tag") == []
    assert filter_completed(empty_nodes) == []
