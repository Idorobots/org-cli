"""Tests for the filter_nodes() function."""

from orgstats.cli import filter_nodes


class MockNode:
    """Mock node object for testing filter_nodes()."""

    def __init__(self, properties=None):
        self.properties = properties if properties is not None else {}


def test_filter_nodes_all_returns_all():
    """Test that 'all' filter returns all nodes."""
    nodes = [
        MockNode(properties={"gamify_exp": "5"}),
        MockNode(properties={"gamify_exp": "15"}),
        MockNode(properties={"gamify_exp": "25"}),
        MockNode(properties={}),
    ]

    result = filter_nodes(nodes, "all")

    assert len(result) == 4
    assert result == nodes


def test_filter_nodes_simple_filters_correctly():
    """Test that 'simple' filter returns nodes with gamify_exp < 10."""
    nodes = [
        MockNode(properties={"gamify_exp": "5"}),
        MockNode(properties={"gamify_exp": "9"}),
        MockNode(properties={"gamify_exp": "10"}),
        MockNode(properties={"gamify_exp": "15"}),
        MockNode(properties={"gamify_exp": "25"}),
    ]

    result = filter_nodes(nodes, "simple")

    assert len(result) == 2
    assert result[0] == nodes[0]
    assert result[1] == nodes[1]


def test_filter_nodes_regular_filters_correctly():
    """Test that 'regular' filter returns nodes with 10 <= gamify_exp < 20."""
    nodes = [
        MockNode(properties={"gamify_exp": "5"}),
        MockNode(properties={"gamify_exp": "10"}),
        MockNode(properties={"gamify_exp": "15"}),
        MockNode(properties={"gamify_exp": "19"}),
        MockNode(properties={"gamify_exp": "20"}),
        MockNode(properties={"gamify_exp": "25"}),
    ]

    result = filter_nodes(nodes, "regular")

    assert len(result) == 3
    assert result[0] == nodes[1]
    assert result[1] == nodes[2]
    assert result[2] == nodes[3]


def test_filter_nodes_hard_filters_correctly():
    """Test that 'hard' filter returns nodes with gamify_exp >= 20."""
    nodes = [
        MockNode(properties={"gamify_exp": "5"}),
        MockNode(properties={"gamify_exp": "15"}),
        MockNode(properties={"gamify_exp": "19"}),
        MockNode(properties={"gamify_exp": "20"}),
        MockNode(properties={"gamify_exp": "25"}),
        MockNode(properties={"gamify_exp": "100"}),
    ]

    result = filter_nodes(nodes, "hard")

    assert len(result) == 3
    assert result[0] == nodes[3]
    assert result[1] == nodes[4]
    assert result[2] == nodes[5]


def test_filter_nodes_boundary_values():
    """Test boundary values for difficulty classification."""
    nodes = [
        MockNode(properties={"gamify_exp": "9"}),
        MockNode(properties={"gamify_exp": "10"}),
        MockNode(properties={"gamify_exp": "19"}),
        MockNode(properties={"gamify_exp": "20"}),
    ]

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


def test_filter_nodes_missing_gamify_exp_treated_as_regular():
    """Test that nodes without gamify_exp are treated as regular."""
    nodes = [
        MockNode(properties={}),
        MockNode(properties={"gamify_exp": "15"}),
        MockNode(properties={"other_property": "value"}),
    ]

    simple_result = filter_nodes(nodes, "simple")
    regular_result = filter_nodes(nodes, "regular")
    hard_result = filter_nodes(nodes, "hard")

    assert len(simple_result) == 0

    assert len(regular_result) == 3
    assert nodes[0] in regular_result
    assert nodes[1] in regular_result
    assert nodes[2] in regular_result

    assert len(hard_result) == 0


def test_filter_nodes_invalid_gamify_exp_treated_as_regular():
    """Test that nodes with invalid gamify_exp are treated as regular."""
    nodes = [
        MockNode(properties={"gamify_exp": "invalid"}),
        MockNode(properties={"gamify_exp": "abc"}),
        MockNode(properties={"gamify_exp": ""}),
    ]

    simple_result = filter_nodes(nodes, "simple")
    regular_result = filter_nodes(nodes, "regular")
    hard_result = filter_nodes(nodes, "hard")

    assert len(simple_result) == 0
    assert len(regular_result) == 3
    assert len(hard_result) == 0


def test_filter_nodes_empty_list():
    """Test filtering an empty list returns empty list."""
    nodes = []

    assert filter_nodes(nodes, "all") == []
    assert filter_nodes(nodes, "simple") == []
    assert filter_nodes(nodes, "regular") == []
    assert filter_nodes(nodes, "hard") == []


def test_filter_nodes_tuple_format():
    """Test that (X Y) format is parsed correctly."""
    nodes = [
        MockNode(properties={"gamify_exp": "(5 10)"}),
        MockNode(properties={"gamify_exp": "(15 20)"}),
        MockNode(properties={"gamify_exp": "(25 30)"}),
    ]

    simple_result = filter_nodes(nodes, "simple")
    regular_result = filter_nodes(nodes, "regular")
    hard_result = filter_nodes(nodes, "hard")

    assert len(simple_result) == 1
    assert simple_result[0] == nodes[0]

    assert len(regular_result) == 1
    assert regular_result[0] == nodes[1]

    assert len(hard_result) == 1
    assert hard_result[0] == nodes[2]


def test_filter_nodes_mixed_list():
    """Test filtering a mixed list with various gamify_exp values."""
    nodes = [
        MockNode(properties={"gamify_exp": "5"}),
        MockNode(properties={"gamify_exp": "15"}),
        MockNode(properties={"gamify_exp": "25"}),
        MockNode(properties={}),
        MockNode(properties={"gamify_exp": "invalid"}),
        MockNode(properties={"gamify_exp": "(8 12)"}),
        MockNode(properties={"gamify_exp": "(18 22)"}),
    ]

    simple_result = filter_nodes(nodes, "simple")
    regular_result = filter_nodes(nodes, "regular")
    hard_result = filter_nodes(nodes, "hard")

    assert len(simple_result) == 2
    assert len(regular_result) == 4
    assert len(hard_result) == 1


def test_filter_nodes_preserves_order():
    """Test that filtering preserves the original order of nodes."""
    nodes = [
        MockNode(properties={"gamify_exp": "5"}),
        MockNode(properties={"gamify_exp": "8"}),
        MockNode(properties={"gamify_exp": "3"}),
        MockNode(properties={"gamify_exp": "9"}),
    ]

    result = filter_nodes(nodes, "simple")

    assert len(result) == 4
    assert result[0] == nodes[0]
    assert result[1] == nodes[1]
    assert result[2] == nodes[2]
    assert result[3] == nodes[3]


def test_filter_nodes_all_simple():
    """Test filtering when all nodes are simple."""
    nodes = [
        MockNode(properties={"gamify_exp": "1"}),
        MockNode(properties={"gamify_exp": "5"}),
        MockNode(properties={"gamify_exp": "9"}),
    ]

    simple_result = filter_nodes(nodes, "simple")
    regular_result = filter_nodes(nodes, "regular")
    hard_result = filter_nodes(nodes, "hard")

    assert len(simple_result) == 3
    assert len(regular_result) == 0
    assert len(hard_result) == 0


def test_filter_nodes_all_regular():
    """Test filtering when all nodes are regular."""
    nodes = [
        MockNode(properties={"gamify_exp": "10"}),
        MockNode(properties={"gamify_exp": "15"}),
        MockNode(properties={"gamify_exp": "19"}),
    ]

    simple_result = filter_nodes(nodes, "simple")
    regular_result = filter_nodes(nodes, "regular")
    hard_result = filter_nodes(nodes, "hard")

    assert len(simple_result) == 0
    assert len(regular_result) == 3
    assert len(hard_result) == 0


def test_filter_nodes_all_hard():
    """Test filtering when all nodes are hard."""
    nodes = [
        MockNode(properties={"gamify_exp": "20"}),
        MockNode(properties={"gamify_exp": "50"}),
        MockNode(properties={"gamify_exp": "100"}),
    ]

    simple_result = filter_nodes(nodes, "simple")
    regular_result = filter_nodes(nodes, "regular")
    hard_result = filter_nodes(nodes, "hard")

    assert len(simple_result) == 0
    assert len(regular_result) == 0
    assert len(hard_result) == 3
