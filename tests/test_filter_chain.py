"""Integration tests for filter chain and combinations."""

from datetime import datetime

from orgstats.filters import (
    filter_completed,
    filter_date_from,
    filter_date_until,
    filter_gamify_exp_above,
    filter_gamify_exp_below,
    filter_property,
    filter_repeats_above,
    filter_tag,
)
from tests.conftest import node_from_org


def test_multiple_filters_applied_sequentially() -> None:
    """Test that multiple filters are applied in sequence."""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 5\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 15\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 25\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 35\n:END:\n")
    )

    result = nodes
    result = filter_gamify_exp_above(result, 10)
    result = filter_gamify_exp_below(result, 30)

    assert len(result) == 2
    assert result[0] == nodes[1]
    assert result[1] == nodes[2]


def test_preset_simple_equivalent() -> None:
    """Test that preset 'simple' is equivalent to filter_gamify_exp_below(10)."""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 5\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 9\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 10\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 15\n:END:\n")
    )

    result = filter_gamify_exp_below(nodes, 10)

    assert len(result) == 2
    assert result[0] == nodes[0]
    assert result[1] == nodes[1]


def test_preset_regular_equivalent() -> None:
    """Test that preset 'regular' is equivalent to above(9) + below(20)."""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 5\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 10\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 15\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 20\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 25\n:END:\n")
    )

    result = nodes
    result = filter_gamify_exp_above(result, 9)
    result = filter_gamify_exp_below(result, 20)

    assert len(result) == 2
    assert result[0] == nodes[1]
    assert result[1] == nodes[2]


def test_preset_hard_equivalent() -> None:
    """Test that preset 'hard' is equivalent to filter_gamify_exp_above(19)."""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 15\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 19\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 20\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 25\n:END:\n")
    )

    result = filter_gamify_exp_above(nodes, 19)

    assert len(result) == 2
    assert result[0] == nodes[2]
    assert result[1] == nodes[3]


def test_combining_exp_and_date_filters() -> None:
    """Test combining gamify_exp and date filters."""
    org_text_jan_simple = (
        "* DONE Task\nCLOSED: [2025-01-15 Wed 10:00]\n:PROPERTIES:\n:gamify_exp: 5\n:END:\n"
    )
    org_text_jan_hard = (
        "* DONE Task\nCLOSED: [2025-01-20 Mon 10:00]\n:PROPERTIES:\n:gamify_exp: 25\n:END:\n"
    )
    org_text_feb_simple = (
        "* DONE Task\nCLOSED: [2025-02-15 Sat 10:00]\n:PROPERTIES:\n:gamify_exp: 5\n:END:\n"
    )

    nodes = (
        node_from_org(org_text_jan_simple)
        + node_from_org(org_text_jan_hard)
        + node_from_org(org_text_feb_simple)
    )

    result = nodes
    result = filter_gamify_exp_below(result, 10)
    result = filter_date_from(result, datetime(2025, 1, 31))

    assert len(result) == 1
    assert result[0] == nodes[2]


def test_combining_tag_and_property_filters() -> None:
    """Test combining tag and property filters."""
    nodes = (
        node_from_org("* DONE Task :tag1:\n:PROPERTIES:\n:custom_prop: value1\n:END:\n")
        + node_from_org("* DONE Task :tag1:\n:PROPERTIES:\n:custom_prop: value2\n:END:\n")
        + node_from_org("* DONE Task :tag2:\n:PROPERTIES:\n:custom_prop: value1\n:END:\n")
    )

    result = nodes
    result = filter_tag(result, "tag1")
    result = filter_property(result, "custom_prop", "value1")

    assert len(result) == 1
    assert result[0] == nodes[0]


def test_multiple_property_filters_and_logic() -> None:
    """Test multiple property filters with AND logic."""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:prop1: value1\n:prop2: value2\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:prop1: value1\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:prop2: value2\n:END:\n")
    )

    result = nodes
    result = filter_property(result, "prop1", "value1")
    result = filter_property(result, "prop2", "value2")

    assert len(result) == 1
    assert result[0] == nodes[0]


def test_multiple_tag_filters_and_logic() -> None:
    """Test multiple tag filters with AND logic."""
    nodes = (
        node_from_org("* DONE Task :tag1:tag2:\n")
        + node_from_org("* DONE Task :tag1:\n")
        + node_from_org("* DONE Task :tag2:\n")
    )

    result = nodes
    result = filter_tag(result, "tag1")
    result = filter_tag(result, "tag2")

    assert len(result) == 1
    assert result[0] == nodes[0]


def test_combining_completion_and_exp_filters() -> None:
    """Test combining completion status and exp filters."""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 15\n:END:\n")
        + node_from_org("* TODO Task\n:PROPERTIES:\n:gamify_exp: 15\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 5\n:END:\n")
    )

    result = nodes
    result = filter_completed(result)
    result = filter_gamify_exp_above(result, 10)

    assert len(result) == 1
    assert result[0] == nodes[0]


def test_date_range_filter() -> None:
    """Test filtering by date range (from + until)."""
    org_text_jan = "* DONE Task\nCLOSED: [2025-01-15 Wed 10:00]\n"
    org_text_feb = "* DONE Task\nCLOSED: [2025-02-15 Sat 10:00]\n"
    org_text_mar = "* DONE Task\nCLOSED: [2025-03-15 Sat 10:00]\n"

    nodes = node_from_org(org_text_jan) + node_from_org(org_text_feb) + node_from_org(org_text_mar)

    result = nodes
    result = filter_date_from(result, datetime(2025, 1, 31))
    result = filter_date_until(result, datetime(2025, 3, 1))

    assert len(result) == 1
    assert result[0] == nodes[1]


def test_repeats_and_exp_filter() -> None:
    """Test combining repeat count and exp filters."""
    org_text_repeats = """* DONE Task
:PROPERTIES:
:gamify_exp: 20
:END:
:LOGBOOK:
- State "DONE" from "TODO" [2025-01-10 Fri 09:00]
- State "DONE" from "TODO" [2025-01-12 Sun 11:00]
:END:
"""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 20\n:END:\n")
        + node_from_org(org_text_repeats)
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 5\n:END:\n")
    )

    result = nodes
    result = filter_repeats_above(result, 1)
    result = filter_gamify_exp_above(result, 10)

    assert len(result) == 1
    assert result[0] == nodes[1]


def test_filters_reduce_to_empty() -> None:
    """Test that conflicting filters can reduce to empty list."""
    nodes = node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 15\n:END:\n") + node_from_org(
        "* DONE Task\n:PROPERTIES:\n:gamify_exp: 25\n:END:\n"
    )

    result = nodes
    result = filter_gamify_exp_above(result, 10)
    result = filter_gamify_exp_below(result, 10)

    assert len(result) == 0


def test_filter_order_matters() -> None:
    """Test that filter application order matters for performance, not correctness."""
    nodes = (
        node_from_org("* DONE Task :tag1:\n:PROPERTIES:\n:gamify_exp: 15\n:END:\n")
        + node_from_org("* DONE Task :tag2:\n:PROPERTIES:\n:gamify_exp: 25\n:END:\n")
        + node_from_org("* DONE Task :tag1:\n:PROPERTIES:\n:gamify_exp: 5\n:END:\n")
    )

    result1 = nodes
    result1 = filter_tag(result1, "tag1")
    result1 = filter_gamify_exp_above(result1, 10)

    result2 = nodes
    result2 = filter_gamify_exp_above(result2, 10)
    result2 = filter_tag(result2, "tag1")

    assert len(result1) == len(result2)
    assert result1[0] == result2[0]


def test_complex_filter_combination() -> None:
    """Test complex combination of many filters."""
    org_text = """* DONE Task :tag1:tag2:
CLOSED: [2025-01-15 Wed 10:00]
:PROPERTIES:
:gamify_exp: 15
:custom_prop: value1
:END:
"""
    org_text_exclude = """* DONE Task :tag1:
CLOSED: [2025-01-15 Wed 10:00]
:PROPERTIES:
:gamify_exp: 25
:custom_prop: value1
:END:
"""
    nodes = node_from_org(org_text) + node_from_org(org_text_exclude)

    result = nodes
    result = filter_completed(result)
    result = filter_tag(result, "tag1")
    result = filter_tag(result, "tag2")
    result = filter_gamify_exp_above(result, 10)
    result = filter_gamify_exp_below(result, 20)
    result = filter_property(result, "custom_prop", "value1")
    result = filter_date_from(result, datetime(2025, 1, 1))
    result = filter_date_until(result, datetime(2025, 2, 1))

    assert len(result) == 1
    assert result[0] == nodes[0]


def test_all_filters_with_empty_input() -> None:
    """Test that all filters handle empty input correctly."""
    import orgparse

    empty_nodes: list[orgparse.node.OrgNode] = []

    assert filter_gamify_exp_above(empty_nodes, 10) == []
    assert filter_gamify_exp_below(empty_nodes, 10) == []
    assert filter_repeats_above(empty_nodes, 1) == []
    assert filter_date_from(empty_nodes, datetime(2025, 1, 1)) == []
    assert filter_date_until(empty_nodes, datetime(2025, 12, 31)) == []
    assert filter_property(empty_nodes, "prop", "value") == []
    assert filter_tag(empty_nodes, "tag") == []
    assert filter_completed(empty_nodes) == []
