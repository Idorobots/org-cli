"""Tests for the filter_nodes() function."""

from typing import Any

from orgstats.cli import filter_nodes
from tests.conftest import node_from_org


def test_filter_nodes_all_returns_all() -> None:
    """Test that 'all' filter returns all nodes."""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 5\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 15\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 25\n:END:\n")
        + node_from_org("* DONE Task\n")
    )

    result = filter_nodes(nodes, "all")

    assert len(result) == 4
    assert result == nodes


def test_filter_nodes_simple_filters_correctly() -> None:
    """Test that 'simple' filter returns nodes with gamify_exp < 10."""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 5\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 9\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 10\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 15\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 25\n:END:\n")
    )

    result = filter_nodes(nodes, "simple")

    assert len(result) == 2
    assert result[0] == nodes[0]
    assert result[1] == nodes[1]


def test_filter_nodes_regular_filters_correctly() -> None:
    """Test that 'regular' filter returns nodes with 10 <= gamify_exp < 20."""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 5\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 10\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 15\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 19\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 20\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 25\n:END:\n")
    )

    result = filter_nodes(nodes, "regular")

    assert len(result) == 3
    assert result[0] == nodes[1]
    assert result[1] == nodes[2]
    assert result[2] == nodes[3]


def test_filter_nodes_hard_filters_correctly() -> None:
    """Test that 'hard' filter returns nodes with gamify_exp >= 20."""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 5\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 15\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 19\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 20\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 25\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 100\n:END:\n")
    )

    result = filter_nodes(nodes, "hard")

    assert len(result) == 3
    assert result[0] == nodes[3]
    assert result[1] == nodes[4]
    assert result[2] == nodes[5]


def test_filter_nodes_boundary_values() -> None:
    """Test boundary values for difficulty classification."""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 9\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 10\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 19\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 20\n:END:\n")
    )

    simple_result = filter_nodes(nodes, "simple")
    regular_result = filter_nodes(nodes, "regular")
    hard_result = filter_nodes(nodes, "hard")

    assert len(simple_result) == 1
    assert simple_result[0] == nodes[0]

    assert len(regular_result) == 2
    assert regular_result[0] == nodes[1]
    assert regular_result[1] == nodes[2]

    assert len(hard_result) == 1
    assert hard_result[0] == nodes[3]


def test_filter_nodes_missing_gamify_exp_treated_as_regular() -> None:
    """Test that nodes without gamify_exp are treated as regular."""
    nodes = (
        node_from_org("* DONE Task\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 15\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:other_property: value\n:END:\n")
    )

    simple_result = filter_nodes(nodes, "simple")
    regular_result = filter_nodes(nodes, "regular")
    hard_result = filter_nodes(nodes, "hard")

    assert len(simple_result) == 0

    assert len(regular_result) == 3
    assert nodes[0] in regular_result
    assert nodes[1] in regular_result
    assert nodes[2] in regular_result

    assert len(hard_result) == 0


def test_filter_nodes_invalid_gamify_exp_treated_as_regular() -> None:
    """Test that nodes with invalid gamify_exp are treated as regular."""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: invalid\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: abc\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: \n:END:\n")
    )

    simple_result = filter_nodes(nodes, "simple")
    regular_result = filter_nodes(nodes, "regular")
    hard_result = filter_nodes(nodes, "hard")

    assert len(simple_result) == 0
    assert len(regular_result) == 3
    assert len(hard_result) == 0


def test_filter_nodes_empty_list() -> None:
    """Test filtering an empty list returns empty list."""
    nodes: list[Any] = []

    assert filter_nodes(nodes, "all") == []
    assert filter_nodes(nodes, "simple") == []
    assert filter_nodes(nodes, "regular") == []
    assert filter_nodes(nodes, "hard") == []


def test_filter_nodes_tuple_format() -> None:
    """Test that (X Y) format is parsed correctly."""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: (5 10)\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: (15 20)\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: (25 30)\n:END:\n")
    )

    simple_result = filter_nodes(nodes, "simple")
    regular_result = filter_nodes(nodes, "regular")
    hard_result = filter_nodes(nodes, "hard")

    assert len(simple_result) == 1
    assert simple_result[0] == nodes[0]

    assert len(regular_result) == 1
    assert regular_result[0] == nodes[1]

    assert len(hard_result) == 1
    assert hard_result[0] == nodes[2]


def test_filter_nodes_mixed_list() -> None:
    """Test filtering a mixed list with various gamify_exp values."""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 5\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 15\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 25\n:END:\n")
        + node_from_org("* DONE Task\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: invalid\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: (8 12)\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: (18 22)\n:END:\n")
    )

    simple_result = filter_nodes(nodes, "simple")
    regular_result = filter_nodes(nodes, "regular")
    hard_result = filter_nodes(nodes, "hard")

    assert len(simple_result) == 2
    assert len(regular_result) == 4
    assert len(hard_result) == 1


def test_filter_nodes_preserves_order() -> None:
    """Test that filtering preserves the original order of nodes."""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 5\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 8\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 3\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 9\n:END:\n")
    )

    result = filter_nodes(nodes, "simple")

    assert len(result) == 4
    assert result[0] == nodes[0]
    assert result[1] == nodes[1]
    assert result[2] == nodes[2]
    assert result[3] == nodes[3]


def test_filter_nodes_all_simple() -> None:
    """Test filtering when all nodes are simple."""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 1\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 5\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 9\n:END:\n")
    )

    simple_result = filter_nodes(nodes, "simple")
    regular_result = filter_nodes(nodes, "regular")
    hard_result = filter_nodes(nodes, "hard")

    assert len(simple_result) == 3
    assert len(regular_result) == 0
    assert len(hard_result) == 0


def test_filter_nodes_all_regular() -> None:
    """Test filtering when all nodes are regular."""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 10\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 15\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 19\n:END:\n")
    )

    simple_result = filter_nodes(nodes, "simple")
    regular_result = filter_nodes(nodes, "regular")
    hard_result = filter_nodes(nodes, "hard")

    assert len(simple_result) == 0
    assert len(regular_result) == 3
    assert len(hard_result) == 0


def test_filter_nodes_all_hard() -> None:
    """Test filtering when all nodes are hard."""
    nodes = (
        node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 20\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 50\n:END:\n")
        + node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 100\n:END:\n")
    )

    simple_result = filter_nodes(nodes, "simple")
    regular_result = filter_nodes(nodes, "regular")
    hard_result = filter_nodes(nodes, "hard")

    assert len(simple_result) == 0
    assert len(regular_result) == 0
    assert len(hard_result) == 3
