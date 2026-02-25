"""Tests for numeric gamify_exp preprocessing."""

from org.filters import preprocess_numeric_gamify_exp
from tests.conftest import node_from_org


def test_preprocess_numeric_gamify_exp_keeps_numeric_values() -> None:
    """Numeric string values should become numeric integers."""
    nodes = node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: 12\n:END:\n")

    processed = preprocess_numeric_gamify_exp(nodes)

    assert processed[0].properties["gamify_exp"] == 12


def test_preprocess_numeric_gamify_exp_converts_tuple_values() -> None:
    """Tuple values should be rewritten to the first integer."""
    nodes = node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: (25 30)\n:END:\n")

    processed = preprocess_numeric_gamify_exp(nodes)

    assert processed[0].properties["gamify_exp"] == 25


def test_preprocess_numeric_gamify_exp_removes_invalid_values() -> None:
    """Invalid gamify_exp values should be removed."""
    nodes = node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: abc\n:END:\n")

    processed = preprocess_numeric_gamify_exp(nodes)

    assert "gamify_exp" not in processed[0].properties


def test_preprocess_numeric_gamify_exp_requires_two_numeric_tuple_values() -> None:
    """Tuple values with non-numeric members should be removed."""
    nodes = node_from_org("* DONE Task\n:PROPERTIES:\n:gamify_exp: (10 nope)\n:END:\n")

    processed = preprocess_numeric_gamify_exp(nodes)

    assert "gamify_exp" not in processed[0].properties
